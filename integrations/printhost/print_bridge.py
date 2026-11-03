"""Authenticated, fixed-queue, single-copy laminated label bridge."""
import hashlib,hmac,json,subprocess,threading,time,re,argparse
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path.home()/'platelink-print';LOCK=threading.Lock()
def command(path):
    return ['lp','-d','Brother_PTP950NW_36mm','-n','1','-t','PlateLink - Placa física','-o','PageSize=Custom.36x62mm','-o','orientation-requested=4','-o','fit-to-page','-o','AutoCut=True','-o','HalfCut=True','-o','RequireMatchingLabelSize=True',str(path)]
def submit(data,key,runner=subprocess.run):
    digest=hashlib.sha256(data).hexdigest()
    with LOCK:
        ledger=ROOT/'jobs.json';jobs=json.loads(ledger.read_text()) if ledger.exists() else {}
        if key in jobs:
            if jobs[key]['sha']!=digest:raise ValueError('La solicitud ya corresponde a otra etiqueta')
            return dict(jobs[key],duplicate=True)
        path=ROOT/(digest+'.pdf');path.write_bytes(data)
        jobs[key]={'ok':False,'sha':digest,'error':'Envío pendiente o sin confirmar; revisa PrintHost antes de repetir'}
        ledger.write_text(json.dumps(jobs))
        done=runner(command(path),capture_output=True,text=True,check=True,timeout=20)
        result={'ok':True,'job':done.stdout.strip(),'sha':digest,'time':time.time(),'printer':'Brother_PTP950NW_36mm'}
        jobs[key]=result
        temp=ROOT/'jobs.tmp';temp.write_text(json.dumps(dict(list(jobs.items())[-1000:])));temp.replace(ledger)
        return result
class Handler(BaseHTTPRequestHandler):
    def reply(self,code,value):
        body=json.dumps(value).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path!='/health':return self.reply(404,{'error':'Ruta inválida'})
        self.reply(200,{'ok':True,'printer':'Brother_PTP950NW_36mm','media':'36 x 62 mm'})
    def do_POST(self):
        if self.path!='/print':return self.reply(404,{'error':'Ruta inválida'})
        if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+(ROOT/'token').read_text().strip()):return self.reply(403,{'error':'No autorizado'})
        try:
            size=int(self.headers.get('Content-Length','0'));key=self.headers.get('Idempotency-Key','')
            if not 100<size<500000 or not re.fullmatch(r'[a-f0-9-]{36}',key):raise ValueError('Solicitud inválida')
            data=self.rfile.read(size)
            if not data.startswith(b'%PDF-'):raise ValueError('Se requiere PDF')
            self.reply(200,submit(data,key))
        except subprocess.TimeoutExpired:self.reply(504,{'error':'CUPS no confirmó el trabajo; revisa PrintHost antes de repetir'})
        except Exception:self.reply(400,{'error':'No se pudo enviar la etiqueta a CUPS'})
    def log_message(self,*args):pass
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8132);a=p.parse_args();ROOT.mkdir(exist_ok=True);ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
