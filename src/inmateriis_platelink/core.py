"""PlateLink: local physical-plate register. No printer command or consumption API."""
import base64
import datetime
import html
import json
import math
import os
from pathlib import Path
from .textures import TEXTURES,texture_for
import re
import sqlite3
import sys
import uuid

VERSION = '0.4.0b2'
BED_TYPES = ('Cool Plate','Engineering Plate','High Temp Plate','Textured PEI Plate','Textured Cool Plate','Supertack Plate')
EVENTS = ('print','cleaning','wear','damage','adhesion','maintenance')

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def data_root():
    for p in Path(__file__).resolve().parents:
        if p.name == 'orca_plugins': return p.parent / 'platelink_inmateriis'
    if sys.platform == 'darwin': root=Path.home()/'Library/Application Support/OrcaSlicer'
    elif sys.platform == 'win32': root=Path(os.environ['APPDATA'])/'OrcaSlicer'
    else: root=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'OrcaSlicer'
    return root/'platelink_inmateriis'

def text(value,maximum=1000,required=False):
    value=str(value or '').strip()
    if len(value)>maximum or required and not value:raise ValueError('Texto ausente o demasiado largo')
    return value

def number(value,maximum,allow_zero=False):
    try:n=float(value)
    except (TypeError,ValueError):raise ValueError('Número inválido')
    if not math.isfinite(n) or n<0 or (not allow_zero and n==0) or n>maximum:raise ValueError('Número fuera de rango')
    return n

def optional_number(value,maximum):
    return None if value in (None,'') else number(value,maximum)

def photo(value):
    if not value:return ''
    if not isinstance(value,str) or len(value)>2800000:raise ValueError('Foto demasiado grande; máximo 2 MB')
    m=re.fullmatch(r'data:image/(png|jpeg);base64,([A-Za-z0-9+/=\r\n]+)',value)
    if not m:raise ValueError('Solo fotos PNG/JPEG, no SVG ni enlaces externos')
    try:b=base64.b64decode(m[2],validate=True)
    except ValueError:raise ValueError('Foto inválida')
    if len(b)>2*1024*1024 or not (b.startswith(b'\x89PNG\r\n\x1a\n') if m[1]=='png' else b.startswith(b'\xff\xd8\xff')):raise ValueError('Imagen inválida')
    return value

def parse_plate(value):
    faces=value.get('faces',[])
    if not isinstance(faces,list) or not 1<=len(faces)<=2:raise ValueError('Registra una o dos caras')
    clean=[]
    for i,face in enumerate(faces):
        bed=face.get('bed_type')
        if bed not in (None,'') and bed not in BED_TYPES:raise ValueError('Tipo de cama Orca desconocido')
        texture=face.get('texture_id') or ''
        if texture and texture not in TEXTURES:raise ValueError('Textura visual desconocida')
        clean.append({'texture_id':texture,'id':'AB'[i],'surface':text(face.get('surface'),120,True),'bed_type':bed,
                      'photo':photo(face.get('photo')),'notes':text(face.get('notes'),2000)})
    compatible=value.get('compatible_printers',[])
    if not isinstance(compatible,list) or len(compatible)>30:raise ValueError('Compatibilidad inválida')
    compatible=list(dict.fromkeys(text(n,120,True) for n in compatible))
    return {'compatible_printers':compatible,'code':text(value.get('code'),80,True),'name':text(value.get('name'),120,True),
            'width':optional_number(value.get('width'),2000),'depth':optional_number(value.get('depth'),2000),
            'thickness':optional_number(value.get('thickness'),50),'faces':clean,'notes':text(value.get('notes'),2000)}

def lookup(state,identifier):
    identifier=text(identifier,200).removeprefix('platelink:v1:')
    found=[p for p in state['plates'] if p['id']==identifier or p['code'].casefold()==identifier.casefold()]
    if len(found)!=1:raise ValueError('Placa no encontrada por ID/QR/código')
    return found[0]

def face_of(plate,face):
    try:return next(f for f in plate['faces'] if f['id']==face)
    except StopIteration:raise ValueError('Cara inexistente')

def append_event(state,plate,face,kind,detail):
    state['events'].append({'id':str(uuid.uuid4()),'at':now(),'plate_id':plate['id'],'face':face,'kind':kind,**detail})

def recommendation(state,plate,face,material,spool):
    material=text(material,120)
    recipes=[r for r in state['recipes'] if r['plate_id']==plate['id'] and r['face']==face and r['material'].casefold()==material.casefold()]
    recipes.sort(key=lambda r:(r['status']=='Validada en laboratorio',r['at']),reverse=True)
    if recipes:return {'source':'PlateLink · receta de esta placa y cara',**recipes[0]}
    surface=face_of(plate,face)['surface'];bed=face_of(plate,face)['bed_type']
    physical=next((n for n in ('Vidrio','Fibra de carbono','PCB Perforada') if n.casefold()==surface.casefold()),None)
    ref=(spool or {}).get('surfaces',{}).get(physical,{}) if physical else (spool or {}).get('beds',{}).get(bed,{})
    return {'source':'Spoolman · '+(physical or bed),
            'bed_temp':ref.get('value'),'status':ref.get('status','Sin dato'),
            'notes':(spool or {}).get('temperature_notes','Sin receta registrada para esta combinación'),
            'adhesive':'','preparation':'','release':''}

def review(state,host,spool=None):
    installed=state['assignments'].get(host.get('printer',''))
    if not installed:return {'warnings':['No hay placa registrada como instalada para este perfil de impresora.'],'installed':None}
    p=lookup(state,installed['plate_id']);f=face_of(p,installed['face']);warnings=[]
    if f['bed_type']!=host.get('bed_type'):warnings.append('La cara instalada ('+str(f['bed_type'] or 'tipo Orca pendiente')+') no coincide con Orca ('+str(host.get('bed_type'))+').')
    materials=host.get('materials',[])
    if spool and materials and re.sub(r'[^A-Z0-9]','',spool.get('material','').upper()) not in [re.sub(r'[^A-Z0-9]','',str(m).upper()) for m in materials]:warnings.append('Material de la bobina y del perfil Orca diferentes: revisar la asociación.')
    rec=recommendation(state,p,f['id'],(spool or {}).get('material') or (materials[0] if materials else ''),spool)
    return {'installed':{'plate':p['code'],'plate_id':p['id'],'face':f['id'],'surface':f['surface'],'bed_type':f['bed_type'],'texture_id':texture_for(f)},
            'warnings':warnings,'recommendation':rec,
            'preview':{'orca_bed_type':host.get('bed_type'),'plate_bed_type':f['bed_type'],
                       'orca_bed_temp':host.get('bed_temp'),'suggested_bed_temp':rec.get('bed_temp'),
                       'action':'Solo vista previa. Cambia el tipo de cama en Orca y revisa el perfil; esta beta no aplica ajustes.'}}

class Store:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'inventory.sqlite3'
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO inventory VALUES(1,?)',(json.dumps({'schema':1,'revision':0,'plates':[],'assignments':{},'events':[],'recipes':[]}),))
    def connect(self):return sqlite3.connect(str(self.path),timeout=3)
    def read(self):
        with self.connect() as db:return json.loads(db.execute('SELECT value FROM inventory WHERE id=1').fetchone()[0])
    def update(self,revision,fn):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            state=json.loads(db.execute('SELECT value FROM inventory WHERE id=1').fetchone()[0])
            if state['revision']!=revision:raise ValueError('El inventario cambió. Actualiza antes de guardar')
            result=fn(state);state['revision']+=1
            db.execute('UPDATE inventory SET value=? WHERE id=1',(json.dumps(state,ensure_ascii=False,allow_nan=False),))
            return result
    def add_plate(self,revision,value):
        p=parse_plate(value);p.update(id=str(uuid.uuid4()),created_at=now())
        def change(s):
            if any(x['code'].casefold()==p['code'].casefold() for x in s['plates']):raise ValueError('Ya existe ese código de placa')
            s['plates'].append(p);append_event(s,p,'','registered',{'notes':p['name']});return p['id']
        return self.update(revision,change)
    def edit_plate(self,revision,identifier,value):
        clean=parse_plate(value)
        def change(state):
            plate=lookup(state,identifier)
            if any(p['id']!=plate['id'] and p['code'].casefold()==clean['code'].casefold() for p in state['plates']):raise ValueError('Código duplicado')
            remaining={f['id'] for f in clean['faces']}
            used=[a['face'] for a in state['assignments'].values() if a['plate_id']==plate['id']]
            used += [r['face'] for r in state['recipes'] if r['plate_id']==plate['id']]
            if any(face not in remaining for face in used):raise ValueError('No puedes retirar una cara con asignaciones o recetas registradas')
            if 'compatible_printers' not in value:clean['compatible_printers']=plate.get('compatible_printers',[])
            plate.update(clean);append_event(state,plate,'','updated',{'notes':'Ficha de placa actualizada por operador'})
        self.update(revision,change)
    def mount(self,revision,identifier,face,printer):
        printer=text(printer,120,True)
        def change(s):
            p=lookup(s,identifier);face_of(p,face)
            for machine,a in list(s['assignments'].items()):
                if machine==printer or a['plate_id']==p['id']:
                    old=lookup(s,a['plate_id']);append_event(s,old,a['face'],'unmounted',{'printer':machine})
                    del s['assignments'][machine]
            s['assignments'][printer]={'plate_id':p['id'],'face':face,'at':now()}
            append_event(s,p,face,'mounted',{'printer':printer});return p['id']
        return self.update(revision,change)
    def unmount(self,revision,printer):
        def change(s):
            if printer not in s['assignments']:raise ValueError('No hay placa asignada a esa impresora')
            a=s['assignments'].pop(printer);append_event(s,lookup(s,a['plate_id']),a['face'],'unmounted',{'printer':printer})
        return self.update(revision,change)
    def event(self,revision,identifier,face,kind,notes,hours=0,spool_id=None):
        if kind not in EVENTS:raise ValueError('Tipo de evento inválido')
        detail={'notes':text(notes,2000,True),'hours':number(hours,100000,True),
                'spool_id':int(spool_id) if spool_id not in (None,'') else None}
        if detail['hours'] and kind!='print':raise ValueError('Horas de uso solo en eventos de impresión')
        def change(s):
            p=lookup(s,identifier);face_of(p,face);append_event(s,p,face,kind,detail)
        self.update(revision,change)
    def recipe(self,revision,identifier,face,value):
        status=value.get('status')
        if status not in ('Sugerida sin validar','Validada en laboratorio'):raise ValueError('Estado de receta inválido')
        r={'id':str(uuid.uuid4()),'material':text(value.get('material'),120,True),'bed_temp':number(value.get('bed_temp'),300,True),
           'adhesive':text(value.get('adhesive'),200),'preparation':text(value.get('preparation'),1000),
           'release':text(value.get('release'),1000),'notes':text(value.get('notes'),2000),
           'status':status,'at':now(),'face':face}
        if status=='Validada en laboratorio' and not r['notes']:raise ValueError('Describe la prueba y condiciones de validación')
        def change(s):
            p=lookup(s,identifier);face_of(p,face);r['plate_id']=p['id'];s['recipes'].append(r)
            append_event(s,p,face,'recipe',{'notes':r['material']+' · '+status})
        self.update(revision,change)
    def export(self):
        out=self.root/'exports';out.mkdir(exist_ok=True)
        p=out/('platelink-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
        with p.open('x',encoding='utf-8') as f:json.dump(self.read(),f,ensure_ascii=False,indent=2)
        return str(p)
    def label(self,identifier):
        p=lookup(self.read(),identifier)
        from ._vendor.qrcode import QRCode
        qr=QRCode(border=4);qr.add_data('platelink:v1:'+p['id']);qr.make(fit=True);matrix=qr.get_matrix();n=len(matrix)
        path=' '.join(f'M{x} {y}h1v1h-1z' for y,row in enumerate(matrix) for x,dark in enumerate(row) if dark)
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="240" height="240" shape-rendering="crispEdges"><rect width="{n}" height="{n}" fill="white"/><path d="{path}" fill="black"/></svg>'
        out=self.root/'exports';out.mkdir(exist_ok=True);dest=out/('label-'+p['id']+'.html')
        dest.write_text('<!doctype html><meta charset="utf-8"><title>PlateLink</title><style>body{font:16px system-ui;padding:24px}svg{display:block}@media print{button{display:none}}</style><h1>'+html.escape(p['code'])+'</h1><p>'+html.escape(p['name'])+'</p>'+svg+'<p>'+html.escape('platelink:v1:'+p['id'])+'</p><p>'+str(p['width'])+' × '+str(p['depth'])+' mm · '+str(len(p['faces']))+' cara(s)</p><button onclick="print()">Imprimir etiqueta</button>',encoding='utf-8')
        return {'path':str(dest),'svg':svg,'payload':'platelink:v1:'+p['id']}
