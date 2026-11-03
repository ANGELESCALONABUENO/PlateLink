"""Build a dependency-free wheel, including the vendored QR encoder's license."""
import base64,csv,hashlib,io,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
NAME,VERSION='inmateriis_platelink','0.4.0b2'
DIST=f'{NAME}-{VERSION}.dist-info'
files={str(p.relative_to(ROOT/'src')):p.read_bytes() for p in sorted((ROOT/'src'/NAME).rglob('*')) if p.is_file() and p.suffix in ('.py','.html','.txt','.png','.json','.css','.js','.svg') and '__pycache__' not in p.parts}
files[DIST+'/METADATA']=(f'Metadata-Version: 2.4\nName: inmateriis-platelink\nVersion: {VERSION}\nSummary: PlateLink by Inmateriis - physical plate inventory, faces, QR and history\nAuthor: Inmateriis\nLicense-Expression: AGPL-3.0-only\nLicense-File: LICENSE\nLicense-File: THIRD_PARTY_NOTICES.md\nRequires-Python: >=3.10\nImport-Name: inmateriis_platelink\nDescription-Content-Type: text/plain\n\nLocal physical plate register; no motion, heating, Z offset or consumption commands.\n').encode()
files[DIST+'/WHEEL']=b'Wheel-Version: 1.0\nGenerator: Inmateriis\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
files[DIST+'/licenses/LICENSE']=(ROOT/'LICENSE').read_bytes()
files[DIST+'/licenses/THIRD_PARTY_NOTICES.md']=(ROOT/'THIRD_PARTY_NOTICES.md').read_bytes()
files[DIST+'/top_level.txt']=b'inmateriis_platelink\n'
out=io.StringIO();writer=csv.writer(out,lineterminator='\n')
for n,b in files.items():writer.writerow([n,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(b).digest()).decode().rstrip('='),len(b)])
writer.writerow([DIST+'/RECORD','','']);files[DIST+'/RECORD']=out.getvalue().encode()
target=ROOT/'dist'/f'{NAME}-{VERSION}-py3-none-any.whl';target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
 for n,b in files.items():z.writestr(n,b)
print(target,target.stat().st_size,'bytes')
