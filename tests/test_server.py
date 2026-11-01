import json,pathlib,sys,tempfile,threading,unittest,urllib.request,urllib.error
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from inmateriis_platelink.server import run
class ServerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=run('127.0.0.1',0,self.tmp.name,{'spoolman_url':'','printers':[]});self.t=threading.Thread(target=self.s.serve_forever,daemon=True);self.t.start();self.url='http://127.0.0.1:'+str(self.s.server_port)
 def tearDown(self):self.s.shutdown();self.s.server_close();self.t.join();self.tmp.cleanup()
 def call(self,path,body=None,origin=None):
  headers={'Content-Type':'application/json'}
  if origin:headers['Origin']=origin
  r=urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
  with urllib.request.urlopen(r) as res:return res.read()
 def test_central_write_persists_for_next_client_and_conflict_rejected(self):
  plate={'code':'HT-001','name':'Alta temperatura 1','faces':[{'surface':'Alta temperatura','bed_type':'High Temp Plate'}]}
  d=json.loads(self.call('/api/action',{'action':'add_plate','revision':0,'plate':plate}))
  self.assertEqual(d['messages'][-1]['state']['revision'],1)
  self.assertEqual(json.loads(self.call('/api/state'))['messages'][0]['state']['plates'][0]['width'],None)
  with self.assertRaises(urllib.error.HTTPError):self.call('/api/action',{'action':'add_plate','revision':0,'plate':plate})
 def test_cross_origin_request_rejected(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.call('/api/action',{'action':'refresh'},'https://example.com')
  self.assertEqual(e.exception.code,403)
 def test_browser_has_bridge_and_shared_language(self):
  page=self.call('/').decode();self.assertIn("fetch('/api/action'",page);self.assertIn('Inventario compartido',page);self.assertIn('PCB Perforada',page)
 def test_command_endpoint_does_not_exist(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.call('/printer/gcode/script',{'script':'M104 S250'})
  self.assertEqual(e.exception.code,404)
if __name__=='__main__':unittest.main()
