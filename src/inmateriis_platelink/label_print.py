"""Laminated label preview and explicit PrintHost submission, without printer controls."""
import hashlib,json,re,subprocess,sys,urllib.request,uuid,threading
from pathlib import Path
from .core import Store,lookup
from .bridge import base_url
LABEL_LOCK=threading.RLock()
def settings(root):
    path=Path(root)/'print-config.json'
    if not path.exists():raise ValueError('Configura print-config.json antes de generar etiquetas')
    value=json.loads(path.read_text())
    value['public_url']=base_url(value['public_url'])
    if value.get('bridge_url'):value['bridge_url']=base_url(value['bridge_url'])
    return value
def label(root,identifier):
    with LABEL_LOCK:return _label(root,identifier)

def _label(root,identifier):
    config=settings(root)
    p=lookup(Store(root).read(),identifier)
    data={'code':p['code'],'faces':[{'id':f['id'],'surface':f['surface']} for f in p['faces']], 'url':config['public_url']+'/#plate='+p['id']}
    digest=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    out=Path(root)/'labels';out.mkdir(exist_ok=True)
    pdf=out/(digest+'.pdf');png=out/(digest+'.png')
    if not pdf.exists() or not png.exists():
        # Fixed renderer and fixed output path; no shell interpretation.
        subprocess.run([sys.executable,str(Path(__file__).with_name('render_label.py')),str(pdf)],input=json.dumps(data).encode(),check=True,timeout=15,capture_output=True)
        subprocess.run(['pdftoppm','-scale-to','1200','-singlefile','-png',str(pdf),str(png.with_suffix(''))],check=True,timeout=15,capture_output=True)
    return p,digest,pdf,png

def preview(root,identifier):
    p,digest,pdf,png=label(root,identifier)
    return {'plate_id':p['id'],'code':p['code'],'digest':digest,'image':'/api/labels/'+p['id']+'/preview.png','pdf':'/api/labels/'+p['id']+'/label.pdf','printer':'Brother PT-P950NW','size':'104 × 36 mm','copies':1}

def print_label(root,value):
    if set(value)!={'plate_id','digest','request_id'}:raise ValueError('Solicitud de etiqueta inválida')
    request_id=str(uuid.UUID(value['request_id']))
    p,digest,pdf,_=label(root,value['plate_id'])
    if value['digest']!=digest:raise ValueError('La ficha cambió; vuelve a revisar la etiqueta')
    config=settings(root)
    if not config.get('bridge_url') or not config.get('token'):raise ValueError('Configura el puente PrintHost y su token antes de imprimir')
    req=urllib.request.Request(config['bridge_url']+'/print',data=pdf.read_bytes(),headers={'Content-Type':'application/pdf','Authorization':'Bearer '+config['token'],'Idempotency-Key':request_id},method='POST')
    result=json.load(urllib.request.urlopen(req,timeout=25))
    return {'ok':result.get('ok',False),'job':result.get('job',''),'duplicate':result.get('duplicate',False),'code':p['code'],'message':'Enviada a la cola de PrintHost; salida física no verificada.'}
