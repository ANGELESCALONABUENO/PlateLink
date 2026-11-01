"""Read-only Spoolman bridge; no printer or consumption mutations."""

import concurrent.futures, datetime, json, math, os, re, sys, tempfile, urllib.parse, urllib.request

from pathlib import Path

BED_TYPES = {
    "Cool Plate": "cool_plate_temp", "Engineering Plate": "eng_plate_temp",
    "High Temp Plate": "hot_plate_temp", "Textured PEI Plate": "textured_plate_temp",
    "Textured Cool Plate": "textured_cool_plate_temp", "Supertack Plate": "supertack_plate_temp",
}

def extra_value(extra, key):
    value = extra.get(key)
    try:
        return json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError):
        return None

def bed_recommendations(filament):
    extra = filament.get("extra") or {}
    result = {}
    for name, key in BED_TYPES.items():
        value = extra_value(extra, "inmateriis_" + key)
        status = extra_value(extra, "inmateriis_" + key + "_status") or "Sin dato"
        try:
            number = float(value) if value is not None and not isinstance(value, bool) else None
            if number is not None and (not math.isfinite(number) or number < 0 or number > 200):
                number = None
        except (ValueError, TypeError):
            number = None
        result[name] = {"value": number, "status": status, "key": key}
    return result

SURFACE_FIELDS = {
    "Vidrio": "inmateriis_glass_plate_temp",
    "Fibra de carbono": "inmateriis_carbon_fiber_plate_temp",
    "PCB Perforada": "inmateriis_perforated_pcb_plate_temp",
}

def surface_recommendations(filament, fields=None):
    mapping=dict(SURFACE_FIELDS)
    for f in fields or []:
        key=f.get("key", "")
        if key.startswith("inmateriis_") and key.endswith("_plate_temp") and key not in ("inmateriis_"+v for v in BED_TYPES.values()):
            mapping[f.get("name") or key]=key
    extra=filament.get("extra") or {};result={}
    for name,key in mapping.items():
        value=extra_value(extra,key)
        try:
            value=float(value) if value is not None and not isinstance(value,bool) else None
            if value is not None and (not math.isfinite(value) or value<0 or value>200):value=None
        except (TypeError,ValueError):value=None
        result[name]={"value":value,"status":extra_value(extra,key+"_status") or "Sin dato", "key":key}
    return result

DEFAULT_CONFIG = {"spoolman_url": "", "printers": []}

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if Path(tmp).exists():
            Path(tmp).unlink()

def load_config(root):
    p = Path(root) / "connections.json"
    return validate_config(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else dict(DEFAULT_CONFIG)

def base_url(value):
    value = str(value).strip().rstrip("/")
    u = urllib.parse.urlsplit(value)
    if u.scheme not in ("http", "https") or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ValueError("Usa una URL raíz http(s), sin credenciales, consulta ni fragmento.")
    return value

def validate_config(value):
    if not isinstance(value, dict) or not isinstance(value.get("printers", []), list):
        raise ValueError("Configuración de conexiones inválida")
    result = {"spoolman_url": base_url(value["spoolman_url"]) if value.get("spoolman_url") else "", "printers": []}
    ids = set()
    for p in value.get("printers", []):
        name = str(p.get("name", "")).strip()
        if not name or len(name) > 120 or name in ids or p.get("kind") not in ("moonraker", "duet_dashboard"):
            raise ValueError("Cada equipo necesita nombre único y tipo moonraker o duet_dashboard")
        ids.add(name)
        result["printers"].append({"name": name, "kind": p["kind"], "url": base_url(p.get("url", "")),
                                  "orca_printer": str(p.get("orca_printer", name))})
    if len(ids) > 30:
        raise ValueError("Máximo 30 equipos")
    return result

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("El servidor redirige: configura su URL final explícitamente")

class ReadOnlyClient:
    """Only known read endpoints; no arbitrary methods, bodies or printer command API."""
    def __init__(self, timeout=4):
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect)

    def get(self, base, path):
        allowed = ("/api/v1/spool", "/api/v1/field/filament", "/api/mounted-spools", "/server/spoolman/status",
                   "/printer/objects/query?configfile")
        if path not in allowed:
            raise ValueError("Endpoint de lectura no permitido")
        req = urllib.request.Request(base_url(base) + path, headers={"Accept": "application/json"}, method="GET")
        with self.opener.open(req, timeout=self.timeout) as r:
            b = r.read(8 * 1024 * 1024 + 1)
        if len(b) > 8 * 1024 * 1024:
            raise ValueError("Respuesta demasiado grande")
        return json.loads(b)

def scalar(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value

def option_values(value):
    """Decode Orca's opt_serialize strings; vectors use semicolons/commas."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    text = str(value)
    parts, start, quoted, escaped = [], 0, False, False
    for i, c in enumerate(text):
        if escaped:
            escaped = False
        elif c == "\\":
            escaped = True
        elif c == '"':
            quoted = not quoted
        elif c == ";" and not quoted:
            parts.append(text[start:i])
            start = i + 1
    parts.append(text[start:])
    if len(parts) == 1 and re.fullmatch(r"-?\d+(?:\.\d+)?(?:,-?\d+(?:\.\d+)?)+", text):
        return text.split(",")
    result = []
    for part in parts:
        try:
            result.append(json.loads(part) if part.startswith('"') else part)
        except ValueError:
            raise ValueError("Opción serializada de Orca no reconocida; no se infiere su valor")
    return result

def normalize_spool(s, fields=None):
    f = s.get("filament") or {}
    color = str(f.get("color_hex") or "").lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", color):
        color = None
    return {"id": int(s["id"]), "name": f.get("name") or "Sin nombre", "material": f.get("material") or "",
            "vendor": (f.get("vendor") or {}).get("name", ""), "color": "#" + color[:6].upper() if color else None,
            "remaining_weight": s.get("remaining_weight"), "location": s.get("location") or "",
            "archived": bool(s.get("archived")), "nozzle": f.get("settings_extruder_temp"),
            "bed": f.get("settings_bed_temp"), "filament_id": f.get("id"),
            "beds": bed_recommendations(f), "surfaces": surface_recommendations(f, fields),
            "temperature_notes": extra_value(f.get("extra") or {}, "inmateriis_bed_sources") or "Sin fuente registrada"}

def assignment(client, p):
    try:
        if p["kind"] == "moonraker":
            d = client.get(p["url"], "/server/spoolman/status")["result"]
            if not d.get("spoolman_connected"):
                raise ValueError("Moonraker no está conectado a Spoolman")
            slots = [{"tool": "E0", "spool_id": d.get("spool_id")}]
        else:
            d = client.get(p["url"], "/api/mounted-spools")["assignments"]
            if not isinstance(d, dict) or not all(k in d for k in ("left", "right")):
                raise ValueError("Asignación Duet incompleta")
            slots = [{"tool": t, "spool_id": d[k]} for k, t in (("left", "E0"), ("right", "E1"))]
        for slot in slots:
            v = slot["spool_id"]
            slot["spool_id"] = int(v) if v not in (None, "", 0, "0") else None
        return {**p, "state": "verified", "slots": slots, "error": ""}
    except Exception as e:
        return {**p, "state": "unknown", "slots": [], "error": type(e).__name__ + ": asignación no verificada"}

def inventory(config, client=None):
    client = client or ReadOnlyClient()
    if not config["spoolman_url"]:
        raise ValueError("Configura la URL de Spoolman en Conexiones")
    rows = client.get(config["spoolman_url"], "/api/v1/spool")
    if not isinstance(rows, list):
        raise ValueError("Spoolman no devolvió una lista de bobinas")
    try:
        fields=client.get(config["spoolman_url"], "/api/v1/field/filament")
    except Exception:
        fields=[]
    spools = [normalize_spool(s,fields) for s in rows]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        printers = list(pool.map(lambda p: assignment(client, p), config["printers"]))
    return {"spools": spools, "printers": printers,
            "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
