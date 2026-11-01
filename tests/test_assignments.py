import unittest,tempfile,sys,copy,json,threading,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent.parent/'src'))
from inmateriis_platelink.core import Store
from inmateriis_platelink.lab import assign,snapshot
from inmateriis_platelink.server import run
CONFIG={'spoolman_url':'','printers':[{'orca_printer':n,'name':n,'kind':'moonraker','url':'http://localhost:7125'} for n in ['SE01','SE02','HT09']]}
class AssignmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=self.tmp.name;self.store=Store(self.root)
  for code,compatible in [('A',['SE01','SE02']),('B',['SE01','SE02']),('C',['HT09'])]:self.store.add_plate(self.store.read()['revision'],{'code':code,'name':'Fixture '+code,'compatible_printers':compatible,'faces':[{'surface':'Vidrio','bed_type':'High Temp Plate'},{'surface':'PEI texturizado','bed_type':'Textured PEI Plate'}]})
  self.ids={p['code']:p['id'] for p in self.store.read()['plates']}
 def tearDown(self):self.tmp.cleanup()
 def payload(self,code,printer='SE01',face='A',**extra):return {'revision':self.store.read()['revision'],'plate_id':self.ids[code],'printer':printer,'face':face,**extra}
 def test_change_and_persistence_and_noop(self):
  assign(self.root,CONFIG,self.payload('A'));assign(self.root,CONFIG,self.payload('B',face='B'));self.assertEqual(Store(self.root).read()['assignments']['SE01']['face'],'B')
  before=self.store.read();assign(self.root,CONFIG,self.payload('B',face='B'));self.assertEqual(before,self.store.read())
 def test_compatibility_and_stale_snapshot_and_unknown_printer(self):
  for value in [self.payload('C'),self.payload('A',printer='UNKNOWN'),{**self.payload('A'),'revision':0}]:
   before=self.store.read()
   with self.assertRaises(ValueError):assign(self.root,CONFIG,value)
   self.assertEqual(before,self.store.read())
 def test_transfer_requires_explicit_previous_owner(self):
  assign(self.root,CONFIG,self.payload('A'));before=self.store.read()
  with self.assertRaises(ValueError):assign(self.root,CONFIG,self.payload('A',printer='SE02'))
  self.assertEqual(before,self.store.read());assign(self.root,CONFIG,self.payload('A',printer='SE02',transfer_from='SE01'));self.assertNotIn('SE01',self.store.read()['assignments'])
 def test_old_client_edit_preserves_compatibility(self):
  p=copy.deepcopy(self.store.read()['plates'][0]);p.pop('compatible_printers');self.store.edit_plate(self.store.read()['revision'],p['id'],p);self.assertEqual(self.store.read()['plates'][0]['compatible_printers'],['SE01','SE02'])
 def test_compact_snapshot_has_no_photos_or_connection_urls(self):
  value=json.dumps(snapshot(self.root,CONFIG));self.assertNotIn('localhost',value);self.assertNotIn('data:image',value)
 def test_http_assignment_origin_and_page(self):
  server=run('127.0.0.1',0,self.root,CONFIG);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url='http://127.0.0.1:'+str(server.server_address[1])
  try:
   self.assertIn('Cada placa, en su lugar.',urllib.request.urlopen(url).read().decode())
   req=urllib.request.Request(url+'/api/lab/assign',data=json.dumps(self.payload('A')).encode(),headers={'Content-Type':'application/json'},method='POST');self.assertEqual(json.load(urllib.request.urlopen(req))['assignments']['SE01']['plate_id'],self.ids['A'])
   req=urllib.request.Request(url+'/api/lab/assign',data=b'{}',headers={'Content-Type':'application/json','Origin':'http://untrusted.invalid'},method='POST')
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
   self.assertEqual(e.exception.code,403)
  finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
