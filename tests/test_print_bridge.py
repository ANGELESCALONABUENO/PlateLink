import importlib.util,tempfile,unittest,subprocess,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('bridge',Path(__file__).parent.parent/'integrations/printhost/print_bridge.py');bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();bridge.ROOT=Path(self.temp.name);self.calls=[]
 def tearDown(self):self.temp.cleanup()
 def runjob(self,args,**kwargs):self.calls.append(args);return subprocess.CompletedProcess(args,0,stdout='request id is Brother_PTP950NW_36mm-42 (1 file(s))\n')
 def test_fixed_queue_and_single_copy(self):
  v=bridge.submit(b'%PDF-'+b'0'*150,'a'*36,self.runjob)
  self.assertTrue(v['ok']);args=self.calls[0];self.assertEqual(args[args.index('-d')+1],'Brother_PTP950NW_36mm');self.assertEqual(args[args.index('-n')+1],'1');self.assertIn('PageSize=Custom.36x62mm',args);self.assertIn('RequireMatchingLabelSize=True',args)
 def test_duplicate_key_does_not_reprint(self):
  data=b'%PDF-'+b'0'*150;bridge.submit(data,'b'*36,self.runjob);v=bridge.submit(data,'b'*36,self.runjob);self.assertTrue(v['duplicate']);self.assertEqual(len(self.calls),1)
  with self.assertRaises(ValueError):bridge.submit(b'%PDF-other','b'*36,self.runjob)
 def test_unknown_queue_result_cannot_be_retried_blindly(self):
  def timeout(*args,**kwargs):raise subprocess.TimeoutExpired('lp',20)
  data=b'%PDF-'+b'0'*150
  with self.assertRaises(subprocess.TimeoutExpired):bridge.submit(data,'c'*36,timeout)
  v=bridge.submit(data,'c'*36,self.runjob);self.assertFalse(v['ok']);self.assertTrue(v['duplicate']);self.assertEqual(self.calls,[])
if __name__=='__main__':unittest.main()
