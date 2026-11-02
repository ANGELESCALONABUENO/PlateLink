# PlateLink by Inmateriis

**Know which physical build plate is installed, keep its history, and show its surface in OrcaSlicer.**

PlateLink is an independent beta project: a shared inventory dashboard and an OrcaSlicer Python plugin. It is not a fork of Spoolman and does not require a custom OrcaSlicer build.

## What it does

- Registers each physical plate with a stable ID, code, dimensions, optional photo and one or two faces.
- Assigns plates and faces to printers, with compatibility checks and explicit confirmation before transferring an occupied plate.
- Tracks cleaning, wear, damage, adhesion notes, maintenance and manually recorded printing hours.
- Stores material/surface recipes and distinguishes suggestions from laboratory-validated results.
- Consults Spoolman in read-only mode for materials and temperature references.
- Provides a standalone dashboard that follows the system light/dark theme, with a shared plate picker and conflict detection.
- Supplies five visual bed textures at 70% opacity: engineering, carbon, black glass, textured gold PEI and silver high-temperature plate.
- Optionally generates QR labels and sends one laminated label to a configured PrintHost/CUPS bridge after preview.

### Clear boundaries

| Project | Responsibility |
| --- | --- |
| PrinterLink | Printer/bed STL visualization |
| Spoolman | Spools, materials and existing consumption accounting |
| PlateLink | Physical plates, faces, surface texture and history |

PlateLink does not send movement, heating, Z-offset or 3D-print commands. It does not debit filament consumption. Physical installation is declared by the operator, not detected by a sensor. Applying a visual texture is separate from selecting Orca's bed category; automatic bed-category selection is not provided by this version. Label printing is an explicit optional action to a label printer.

## Run the shared server

Python 3.10+:

```sh
python -m venv .venv
. .venv/bin/activate
pip install .
cp examples/connections.example.json connections.json
# Edit connections.json for your own equipment.
python -m inmateriis_platelink.server --host 127.0.0.1 --port 8812 --data ./data --connections ./connections.json
```

Open http://127.0.0.1:8812/. Start with an empty inventory; no laboratory database or private endpoints are distributed. To share it, bind deliberately to a trusted LAN/VPN interface and protect access there. The inventory service has no user authentication and must not be exposed directly to the public Internet.

On Windows, activate the environment with `.venv\Scripts\activate`. The central server and plugin client can be separate machines. The optional PrintHost adapter requires Linux/CUPS.

## OrcaSlicer plugin

Requires an OrcaSlicer version with Python Script plugins and the preset API used by Orca 2.5.0+. Build the wheel with `python build.py`, import it in Orca's plugin manager, enable the Script capability and press Play.

1. Open **PlateLink · Inventario compartido** and configure the central server URL.
2. Register and assign plates in the shared inventory.
3. Open **PlateLink · Textura de cama instalada** and leave its window open to follow the currently selected printer's installed surface.
4. Save the printer preset when Orca asks if you want the visual reference to persist.

The texture capability writes only `bed_custom_texture`; PrinterLink remains responsible for the STL. Inventory changes do not change the physical printer's settings. Do not infer that a visual bed texture changes slicing temperatures.

The GitHub source is a **0.4.0 beta development snapshot** combining the dashboard and optional label work. It is distinct from the previously published Orca Cloud 0.3.1 plugin. macOS UI has been exercised; updated Windows end-to-end verification and Linux Orca UI testing remain pending. Do not treat platform-independent wheel packaging as completed platform validation.

## Optional laminated labels

See [PrintHost setup](docs/PRINTHOST.md). A label contains the plate code, its surface(s), and a stable QR URL to its inventory record. It omits the current printer so that changing the plate's location does not invalidate the label. The QR opens the private server and therefore requires network access to it.

The dashboard shows a preview, then an explicit **Print one label** action. CUPS queue acceptance is reported separately from physical output. Duplicate request IDs and uncertain submission results are not blindly resubmitted.

## Development and verification

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
python build.py
```

Tests cover SQLite persistence, concurrency conflicts, compatibility, explicit transfers, read-only material use, texture application boundaries, origin checks and label queue idempotency. They do not move a printer or print labels. See [architecture](docs/ARCHITECTURE.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

## En español

Inventario compartido de camas físicas para impresión 3D: identifica cada placa, registra sus caras, asignación, cuidados e historial, y representa su superficie en Orca. Las fotos y bases de datos quedan en tu servidor. Los parámetros de impresión y el descuento de material siguen bajo control de sus integraciones actuales.

## License

AGPL-3.0-only. Bundled third-party code retains its applicable license; see the notices above.

The texture popup checks the installed plate every **15 seconds** while open. It only writes a texture when its local reference differs. Exact subscribed-preset aliases may be configured with `orca_aliases` per printer; names are never matched by stripping an arbitrary bundle namespace.
