"""Automatic texture refresh while the explicitly opened popup is running."""
import json
import threading
import urllib.request
from pathlib import Path
import orca
from .core import data_root
from .bridge import base_url,NoRedirect,write_json
from .textures import selected_assignment,install_texture,apply_texture

PAGE='''<!doctype html><html lang="es"><meta charset="utf-8"><style>body{font:15px system-ui;padding:24px;color:#e9f0f4;background:#18212a}h1{font-size:24px}input,button,select{font:inherit;padding:10px;border-radius:7px;border:1px solid #53616a;background:#253541;color:inherit;margin:5px 0}input[type=url]{width:100%;box-sizing:border-box}button{cursor:pointer}pre{white-space:pre-wrap;line-height:1.6}img{width:120px;height:120px;border-radius:10px;object-fit:cover}#error{color:#ffbf8e}.muted{color:#b8c4cb}</style><h1>PlateLink · Textura instalada</h1><p>La placa y cara registradas en el inventario eligen la textura de la cama de Orca.</p><label>Servidor PlateLink<input id="url" type="url" placeholder="http://servidor:puerto"></label><button id="save">Guardar conexión</button><hr><label><input id="auto" type="checkbox" checked> Seguir la placa instalada mientras esta ventana esté abierta</label><p><select id="printer" aria-label="Perfil de impresora"></select> <button id="select">Seleccionar en Orca</button></p><button id="refresh">Actualizar textura ahora</button><pre id="state">Leyendo selección…</pre><p id="error"></p><img id="preview" hidden alt="Textura visual de la placa instalada"><p class="muted">70 % de opacidad · 30 % de transparencia. Solo cambia «Textura». PrinterLink conserva el modelo 3D. Guarda el perfil cuando Orca lo solicite para conservar la referencia al cerrar. Las temperaturas, el tipo de cama y la calibración permanecen bajo control del operador.</p><script>const $=id=>document.getElementById(id);let busy=false;function send(action,extra={}){if(!busy)orca.postMessage({action,...extra});} $('save').onclick=()=>send('config',{url:$('url').value});$('refresh').onclick=()=>send('refresh');$('select').onclick=()=>send('select',{printer:$('printer').value});setInterval(()=>{if($('auto').checked)send('refresh')},10000);orca.onMessage(d=>{busy=d.type==='busy';for(const id of ['save','select','refresh'])$(id).disabled=busy;if(busy)return;$('error').textContent=d.error||'';if(d.url)$('url').value=d.url;if(d.printers){const old=$('printer').value;$('printer').replaceChildren();for(const name of d.printers){const o=document.createElement('option');o.value=name;o.textContent=name;$('printer').append(o)}$('printer').value=d.printers.includes(old)?old:d.printer;}if(d.text)$('state').textContent=d.text;if(d.preview){$('preview').src=d.preview;$('preview').hidden=false}else if(d.error)$('preview').hidden=true;});send('refresh');</script></html>'''

def snapshot():
 p=orca.host.preset_bundle().current_printer_preset()
 def value(key):
  v=p.config_value(key) or '';return v[0] if isinstance(v,list) and v else v
 return {'printer':p.name,'texture':value('bed_custom_texture'),'model':value('bed_custom_model')}

def read_state(url):
 req=urllib.request.Request(base_url(url)+'/api/texture-state')
 with urllib.request.build_opener(NoRedirect).open(req,timeout=12) as r:raw=r.read(1024*1024+1)
 if len(raw)>1024*1024:raise ValueError('Respuesta de texturas demasiado grande')
 return json.loads(raw)

class TextureWindow(orca.script.ScriptPluginCapabilityBase):
 def get_name(self):return 'PlateLink · Textura de cama instalada'
 def on_load(self):self.window=None;self.busy=False;self.generation=0
 def on_unload(self):self.generation+=1;self.window=None
 def execute(self):
  if self.window and self.window.is_open():self.window.close()
  self.generation+=1;self.busy=False
  self.window=orca.host.ui.create_window(html=PAGE,title='PlateLink · Textura instalada',width=790,height=780,on_message=self.on_message)
  return orca.ExecutionResult.success('PlateLink seguirá la textura de la placa instalada mientras el panel esté abierto')
 def on_message(self,m):
  if not isinstance(m,dict) or self.busy:return
  if m.get('action') not in ('config','refresh','select'):return
  w=self.window;root=data_root();path=root/'server.json';generation=self.generation
  try:
   settings=json.loads(path.read_text()) if path.exists() else {}
   if m['action']=='config':settings['server_url']=base_url(m['url']);write_json(path,settings)
   url=settings.get('server_url','')
   if not url:w.post({'type':'state','error':'Configura el servidor de tu inventario PlateLink para continuar.'});return
   host=snapshot();self.busy=True;w.post({'type':'busy'})
  except Exception as e:w.post({'type':'state','error':str(e)});return
  def post(d):
   if generation==self.generation and w.is_open():w.post(d)
  def work():
   try:
    state=read_state(url);names=[r['printer'] for r in state['printers']]
    if generation!=self.generation or not w.is_open():return
    if m['action']=='select':
     if m.get('printer') not in names:raise ValueError('Perfil no registrado en este inventario')
     orca.host.preset.printer.begin_update(preset_name=m['printer']).commit()
     post({'type':'state','url':url,'printers':names,'printer':m['printer'],'text':'Impresora seleccionada. Actualizando en la siguiente consulta…'});return
    installed=selected_assignment(state,host['printer']);dest=install_texture(root,installed['texture_id'])
    fresh=read_state(url)
    if generation!=self.generation or not w.is_open():return
    changed=apply_texture(installed,fresh,host,orca.host,dest)
    # A small receipt records ownership and the original reference, not a full preset copy.
    receipt=root/'texture-links.json';links=json.loads(receipt.read_text()) if receipt.exists() else {}
    original=links.get(host['printer'],{}).get('original_texture',host['texture'])
    links[host['printer']]={'original_texture':original,'texture':dest,'plate_id':installed['plate_id'],'face':installed['face'],'texture_id':installed['texture_id'],'model_preserved':host['model']};write_json(receipt,links)
    import base64
    preview='data:image/png;base64,'+base64.b64encode(Path(dest).read_bytes()).decode()
    post({'type':'state','url':url,'printers':names,'printer':host['printer'],'preview':preview,'text':host['printer']+'\n'+installed['plate']+' · cara '+installed['face']+' · '+installed['surface']+'\n'+installed['texture_label']+'\n'+('Textura aplicada. Guarda el perfil cuando Orca lo solicite.' if changed else 'Textura actualizada y vinculada.')})
   except Exception as e:post({'type':'state','url':url,'error':str(e)})
   finally:
    if generation==self.generation:self.busy=False
  threading.Thread(target=work,daemon=True,name='PlateLink-texture').start()
