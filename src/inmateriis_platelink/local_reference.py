"""Persist visual references in a subscribed bundle's local cache only.

The cloud profile and its settings are not uploaded or renamed. Cloud may replace
this cache on update; the owning plugin can reconcile its reference again.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def fingerprint(filename):
    p = Path(filename)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ''


def persist_reference(root, filename, name, field, asset, expected_hash):
    if not name.startswith('_subscribed/'):
        return False
    owners = {'bed_custom_model': 'printerlink/assets',
              'bed_custom_texture': 'platelink_inmateriis/textures'}
    if field not in owners:
        raise ValueError('Only visual asset references may be persisted')
    root = Path(root).resolve()
    p = Path(filename)
    try:
        relative = p.resolve().relative_to(root)
        resource = Path(asset).resolve()
        resource.relative_to(root / owners[field])
    except ValueError:
        raise ValueError('Reference is outside the local bundle cache or plugin assets')
    parts = relative.parts
    if (len(parts) != 6 or parts[0] != 'user' or parts[2] != '_subscribed'
            or parts[4] != 'machine' or p.suffix != '.json'
            or name != '_subscribed/' + parts[3] + '/' + p.stem):
        raise ValueError('Subscribed preset identity does not match its cache file')
    if p.is_symlink() or not resource.is_file() or p.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Invalid cached preset or missing visual asset')
    raw = p.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if not expected_hash or digest != expected_hash:
        raise ValueError('The cached preset changed; refresh before linking')
    data = json.loads(raw)
    if data.get('name') not in (p.stem, name):
        raise ValueError('The cached preset name does not match')
    if data.get(field) == resource.as_posix():
        return True
    before = dict(data)
    data[field] = resource.as_posix()
    assert {k:v for k,v in data.items() if k != field} == {k:v for k,v in before.items() if k != field}
    backup = root / owners[field].split('/')[0] / 'local-reference-backups'
    backup.mkdir(parents=True, exist_ok=True)
    backup_file = backup / (digest + '.json')
    if not backup_file.exists():
        backup_file.write_bytes(raw)
    fd, temporary = tempfile.mkstemp(prefix='.visual-reference-', dir=p.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write((json.dumps(data, ensure_ascii=False, indent=4) + '\n').encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        if fingerprint(p) != digest:
            raise ValueError('Cloud updated this cached preset during linking; retry')
        os.replace(temporary, p)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True
