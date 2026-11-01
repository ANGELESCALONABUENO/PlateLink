"""Compact plate inventory and explicit assignment actions for laboratory dashboards."""
import base64
from .core import Store, lookup, face_of
from .textures import texture_for

def snapshot(root, config):
 s=Store(root).read()
 return {'revision':s['revision'],'printers':[p['orca_printer'] for p in config.get('printers',[])],
  'assignments':s['assignments'],'plates':[{'id':p['id'],'code':p['code'],'name':p['name'],
   'width':p.get('width'),'depth':p.get('depth'),'compatible_printers':p.get('compatible_printers',[]),
   'faces':[{'id':f['id'],'surface':f['surface'],'bed_type':f.get('bed_type'),'texture_id':texture_for(f),'has_photo':bool(f.get('photo'))} for f in p['faces']]} for p in s['plates']]}

def assign(root,config,value):
 if not isinstance(value,dict):raise ValueError('Solicitud inválida')
 printer=value.get('printer');known=[p['orca_printer'] for p in config.get('printers',[])]
 if printer not in known:raise ValueError('Impresora no registrada en PlateLink')
 revision=value.get('revision')
 if type(revision) is not int:raise ValueError('Actualiza el inventario antes de guardar')
 store=Store(root);s=store.read()
 if revision!=s['revision']:raise ValueError('El inventario cambió. Actualiza y revisa la selección nuevamente.')
 action=value.get('action','mount')
 if action=='unmount':
  if printer in s['assignments']:store.unmount(revision,printer)
 elif action=='mount':
  p=lookup(s,value.get('plate_id'));face=face_of(p,value.get('face'))
  compatible=p.get('compatible_printers',[])
  if compatible and printer not in compatible:raise ValueError('Esta placa está registrada para otra impresora')
  previous=next((name for name,a in s['assignments'].items() if a['plate_id']==p['id'] and name!=printer),None)
  if previous and value.get('transfer_from')!=previous:raise ValueError('Confirma primero la retirada de '+previous)
  current=s['assignments'].get(printer,{})
  if current.get('plate_id')!=p['id'] or current.get('face')!=face['id']:store.mount(revision,p['id'],face['id'],printer)
 else:raise ValueError('Acción no permitida')
 return snapshot(root,config)

def image(root,identifier,face):
 f=face_of(lookup(Store(root).read(),identifier),face);photo=f.get('photo','')
 if not photo:raise ValueError('Esta cara no tiene fotografía')
 head,data=photo.split(',',1)
 return base64.b64decode(data,validate=True),head.removeprefix('data:').split(';')[0]
