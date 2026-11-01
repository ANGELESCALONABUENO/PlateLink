"""Small central dashboard. Binds an explicitly selected interface, never a printer API."""
import argparse,json,mimetypes,urllib.parse
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .service import dispatch
from .bridge import validate_config
from .core import VERSION
PAGE=Path(__file__).with_name('web').joinpath('dashboard.html').read_text(encoding='utf-8').replace('{{VERSION}}',VERSION)
WEB_BRIDGE='''<script>let receiver=null;window.orca={onMessage:fn=>receiver=fn,close:()=>{},postMessage:async m=>{try{const r=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(m)});const d=await r.json();for(const x of d.messages||[])receiver?.(x);if(d.error)receiver?.({type:'error',message:d.error});}catch(e){receiver?.({type:'error',message:'No se pudo conectar al servidor PlateLink'});}}};</script>'''
class Handler(BaseHTTPRequestHandler):
    server_version='PlateLink/0.1'
    def send(self,status,body,content_type='application/json'):
        self.send_response(status);self.send_header('Content-Type',content_type+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
    def reply(self,status,value):self.send(status,json.dumps(value,ensure_ascii=False).encode())
    def do_GET(self):
        path=urllib.parse.urlsplit(self.path).path
        if path in ('/','/index.html'):
            page=PAGE.replace('<script>',WEB_BRIDGE+'<script>',1).replace('Inventario local. No se sincroniza automáticamente entre computadoras.','Inventario compartido del laboratorio.').replace('Inventario local guardado','Inventario compartido guardado')
            # The central dashboard has no Orca selection and no editable server connection.
            page=page.replace('<button id="settings">Conexiones</button>','<button id="settings" hidden>Conexiones</button>')
            self.send(200,page.encode(),'text/html');return
        if path.startswith('/api/labels/'):
            from .label_print import label,preview
            try:
                parts=path.split('/')
                if len(parts)==4:
                    self.reply(200,preview(self.server.root,parts[3]));return
                if len(parts)==5 and parts[4] in ('preview.png','label.pdf'):
                    _,_,pdf,png=label(self.server.root,parts[3])
                    self.send(200,(png if parts[4]=='preview.png' else pdf).read_bytes(),'image/png' if parts[4]=='preview.png' else 'application/pdf');return
                self.reply(404,{'error':'Etiqueta no encontrada'});return
            except (ValueError,KeyError) as e:self.reply(400,{'error':str(e)});return
            except Exception:self.reply(503,{'error':'No se pudo generar la etiqueta'});return
        if path=='/api/lab/plates':
            from .lab import snapshot
            self.reply(200,snapshot(self.server.root,self.server.config));return
        if path.startswith('/api/lab/photo/'):
            try:
                from .lab import image
                parts=path.split('/')
                if len(parts)!=6:raise ValueError('Ruta inválida')
                data,typ=image(self.server.root,parts[4],parts[5]);self.send(200,data,typ)
            except (ValueError,KeyError):self.reply(404,{'error':'Fotografía no encontrada'})
            return
        if path.startswith('/assets/'):
            name=path.removeprefix('/assets/')
            if not name or '/' in name or name.startswith('.'):self.reply(404,{'error':'Recurso no encontrado'});return
            file=Path(__file__).with_name('web')/'assets'/name
            if not file.is_file():self.reply(404,{'error':'Recurso no encontrado'});return
            self.send(200,file.read_bytes(),mimetypes.guess_type(str(file))[0] or 'application/octet-stream');return
        if path=='/api/health':self.reply(200,{'status':'ok','service':'PlateLink','version':VERSION});return
        if path=='/api/texture-state':
            from .textures import assignment_rows
            from .core import Store
            self.reply(200,assignment_rows(Store(self.server.root).read(),self.server.config));return
        if path.startswith('/textures/'):
            from .textures import ASSETS,TEXTURES
            key=Path(path).stem
            if path!='/textures/'+key+'.png' or key not in TEXTURES:self.reply(404,{'error':'Textura no encontrada'});return
            self.send(200,(ASSETS/(key+'.png')).read_bytes(),'image/png');return
        if path=='/api/state':self.reply(200,{'messages':dispatch(self.server.root,self.server.config,{'action':'refresh'})});return
        if path.startswith('/exports/'):
            name=Path(path).name
            if path!='/exports/'+name or not name.endswith(('.html','.json')):self.reply(404,{'error':'Archivo no encontrado'});return
            file=self.server.root/'exports'/name
            if not file.is_file():self.reply(404,{'error':'Archivo no encontrado'});return
            self.send(200,file.read_bytes(),'text/html' if name.endswith('.html') else 'application/json');return
        self.reply(404,{'error':'Ruta no encontrada'})
    def do_POST(self):
        if self.path not in ('/api/action','/api/lab/assign','/api/labels/print'):self.reply(404,{'error':'Ruta no encontrada'});return
        origin=self.headers.get('Origin')
        if origin and urllib.parse.urlsplit(origin).netloc!=self.headers.get('Host'):
            self.reply(403,{'error':'Origen no permitido'});return
        if 'application/json' not in self.headers.get('Content-Type',''):
            self.reply(415,{'error':'Se requiere JSON'});return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length<=0 or length>6*1024*1024:raise ValueError('Solicitud vacía o demasiado grande')
            m=json.loads(self.rfile.read(length))
            if not isinstance(m,dict):raise ValueError('Solicitud inválida')
            if self.path=='/api/labels/print':
                from .label_print import print_label
                self.reply(200,print_label(self.server.root,m));return
            if self.path=='/api/lab/assign':
                from .lab import assign
                self.reply(200,assign(self.server.root,self.server.config,m));return
            host=m.pop('_orca_host',None)
            if host is not None and not isinstance(host,dict):raise ValueError('Selección Orca inválida')
            self.reply(200,{'messages':dispatch(self.server.root,self.server.config,m,host)})
        except (ValueError,KeyError,TypeError) as e:self.reply(400,{'error':str(e)})
        except Exception as e:self.reply(500,{'error':'No se pudo completar la operación: '+type(e).__name__})
    def log_message(self,fmt,*args):print(self.log_date_time_string(),fmt%args,flush=True)

def run(host,port,root,config):
    server=ThreadingHTTPServer((host,port),Handler);server.root=Path(root);server.config=validate_config(config)
    from .core import Store
    Store(root)
    return server

def main():
    p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--port',type=int,required=True);p.add_argument('--data',required=True);p.add_argument('--connections',required=True);a=p.parse_args()
    config=json.loads(Path(a.connections).read_text());server=run(a.host,a.port,a.data,config)
    print('PlateLink listening on',server.server_address,flush=True);server.serve_forever()
if __name__=='__main__':main()
