"""Visual surface ownership: only bed_custom_texture belongs to PlateLink."""
import hashlib
import json
from pathlib import Path
import os
import unicodedata
from .opacity import opacity70

TEXTURES={
 'engineering':'Ingeniería · negro granulado',
 'carbon':'Fibra de carbono',
 'black-glass':'Vidrio negro',
 'gold-pei':'PEI texturizado · dorado',
 'high-temperature-metal':'Alta temperatura · metal plateado',
}
ASSETS=Path(__file__).parent/'textures'

def surface_texture(surface):
 value=' '.join(''.join(c for c in unicodedata.normalize('NFKD',str(surface)) if not unicodedata.combining(c)).lower().split())
 return {'ingenieria':'engineering','engineering':'engineering','fibra de carbono':'carbon',
         'vidrio':'black-glass','vidrio negro':'black-glass','pei texturizado':'gold-pei',
         'alta temperatura':'high-temperature-metal'}.get(value)

def texture_for(face):
 key=face.get('texture_id') or surface_texture(face.get('surface',''))
 if key and key not in TEXTURES:raise ValueError('Textura no reconocida')
 return key

def assignment_rows(state,config):
 rows=[]
 for connection in config.get('printers',[]):
  name=connection['orca_printer'];a=state.get('assignments',{}).get(name);row={'printer':name,'orca_aliases':connection.get('orca_aliases',[]),'installed':None}
  if a:
   p=next((p for p in state['plates'] if p['id']==a['plate_id']),None)
   f=next((f for f in (p or {}).get('faces',[]) if f['id']==a['face']),None)
   if p and f:row['installed']={'plate_id':p['id'],'plate':p['code'],'face':f['id'],
     'surface':f['surface'],'texture_id':texture_for(f),'texture_label':TEXTURES.get(texture_for(f),'Sin textura asociada')}
  rows.append(row)
 return {'schema':1,'revision':state['revision'],'printers':rows}

def selected_assignment(state,printer):
 rows=[r for r in state.get('printers',[]) if r.get('printer')==printer or printer in r.get('orca_aliases',[])]
 if len(rows)!=1:raise ValueError('Relaciona este perfil exacto de Orca en las conexiones de PlateLink')
 installed=rows[0].get('installed')
 if not installed:raise ValueError('No hay placa y cara registradas como instaladas')
 if installed.get('texture_id') not in TEXTURES:raise ValueError('Asigna una textura visual a esta cara en el inventario')
 return installed

def install_texture(root,key):
 if key not in TEXTURES:raise ValueError('Textura no reconocida')
 src=ASSETS/(key+'.png');data=src.read_bytes()
 info=json.loads((ASSETS/'manifest.json').read_text())[key];expected=info['sha256']
 if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('La textura incluida no pasó la comprobación de integridad')
 # Versioned immutable assets give each platform a local path, without paths from the author.
 expected=info['opacity70_sha256']
 dest=Path(root)/'textures'/('v2-opacity70-'+expected[:12])/(key+'.png');dest.parent.mkdir(parents=True,exist_ok=True)
 if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest()!=expected:
  data=opacity70(data)
  if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('La opacidad de la textura no coincide')
  tmp=dest.with_suffix('.tmp');tmp.write_bytes(data);os.replace(tmp,dest)
 return str(dest)

def apply_texture(expected,fresh,host,api,path):
 current=selected_assignment(fresh,host['printer'])
 if current!=expected:raise ValueError('La placa, cara o textura cambiaron: actualiza antes de aplicar')
 if host.get('texture')==path:return False
 # Do not select a different printer in an automatic background operation.
 tx=api.preset.printer.begin_update()
 if tx.target_name!=host['printer']:raise ValueError('Cambió la impresora seleccionada; no se aplicó la textura')
 tx.set('bed_custom_texture',path)
 result=tx.commit()
 if result.target_name!=host['printer']:raise ValueError('Orca no confirmó el perfil esperado')
 return True
