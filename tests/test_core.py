import copy,json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
from inmateriis_platelink.core import *
PLATE={'code':'PL-001','name':'Placa de prueba','width':220,'depth':220,'thickness':0.5,'faces':[
 {'surface':'PEI liso','bed_type':'High Temp Plate'}, {'surface':'PEI texturizado','bed_type':'Textured PEI Plate'}]}
class PlateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def add(self,p=None):return self.store.add_plate(self.store.read()['revision'],p or PLATE)
 def rev(self):return self.store.read()['revision']
 def test_persistence_and_two_sides(self):
  pid=self.add();state=Store(self.tmp.name).read();self.assertEqual(state['plates'][0]['id'],pid);self.assertEqual(len(state['plates'][0]['faces']),2)
 def test_duplicate_human_ids_and_stale_updates_rejected(self):
  self.add()
  with self.assertRaises(ValueError):self.add()
  with self.assertRaises(ValueError):self.store.mount(0,'PL-001','A','MA01')
 def test_one_location_and_one_plate_per_printer_with_history(self):
  a=self.add();other=copy.deepcopy(PLATE);other['code']='PL-002';b=self.add(other)
  self.store.mount(self.rev(),a,'A','MA01');self.store.mount(self.rev(),a,'B','SE01')
  self.assertNotIn('MA01',self.store.read()['assignments'])
  self.store.mount(self.rev(),b,'A','SE01');state=self.store.read()
  self.assertEqual(state['assignments']['SE01']['plate_id'],b)
  self.assertEqual(len([e for e in state['events'] if e['kind']=='unmounted']),2)
 def test_qr_lookup_and_offline_label(self):
  pid=self.add();label=self.store.label('PL-001')
  self.assertEqual(lookup(self.store.read(),label['payload'])['id'],pid)
  s=pathlib.Path(label['path']).read_text();self.assertIn('shape-rendering="crispEdges"',s);self.assertIn(label['payload'],s)
  self.assertNotIn('https://',s);self.assertNotIn('<script src',s)
 def test_invalid_face_rolls_back(self):
  self.add();rev=self.rev()
  with self.assertRaises(ValueError):self.store.mount(rev,'PL-001','C','MA01')
  self.assertEqual(self.rev(),rev);self.assertEqual(self.store.read()['assignments'],{})
 def test_recipes_specific_to_plate_face_material_and_validated_requires_evidence(self):
  pid=self.add();r={'material':'ABS','bed_temp':120,'status':'Validada en laboratorio','notes':''}
  with self.assertRaises(ValueError):self.store.recipe(self.rev(),pid,'A',r)
  r['notes']='Prueba real anotada por operador';self.store.recipe(self.rev(),pid,'A',r)
  p=lookup(self.store.read(),pid)
  self.assertEqual(recommendation(self.store.read(),p,'A','ABS',None)['bed_temp'],120)
  self.assertIsNone(recommendation(self.store.read(),p,'B','ABS',None)['bed_temp'])
 def test_spoolman_fallback_is_never_lab_validated(self):
  pid=self.add();s=self.store.read();p=lookup(s,pid)
  spool={'beds':{'High Temp Plate':{'value':65,'status':'Sin validar'}},'temperature_notes':'Preferencia del usuario'}
  self.assertEqual(recommendation(s,p,'A','PLA',spool)['status'],'Sin validar')
 def test_bed_mismatch_and_history_hours_no_consumption(self):
  pid=self.add();self.store.mount(self.rev(),pid,'B','MA01')
  self.store.event(self.rev(),pid,'B','print','Impresión de prueba',2.5,118)
  result=review(self.store.read(),{'printer':'MA01','bed_type':'High Temp Plate','materials':['PLA']})
  self.assertTrue(result['warnings']);self.assertEqual(self.store.read()['events'][-1]['hours'],2.5)
  self.assertNotIn('remaining_weight',json.dumps(self.store.read()))
 def test_photo_and_numeric_validation(self):
  for value in ('https://example.com/x.png','data:image/svg+xml;base64,AAAA'):
   with self.assertRaises(ValueError):photo(value)
  for value in (float('nan'),float('inf'),-2,0):
   p=copy.deepcopy(PLATE);p['width']=value
   with self.assertRaises(ValueError):parse_plate(p)
 def test_export_preserves_full_register(self):
  self.add();path=self.store.export();self.assertEqual(json.loads(pathlib.Path(path).read_text()),self.store.read())
if __name__=='__main__':unittest.main()
