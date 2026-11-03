import json,tempfile,unittest
from pathlib import Path
from inmateriis_platelink.local_reference import fingerprint,persist_reference
class LocalReferenceTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.p=self.root/'user/u/_subscribed/b/machine/SE02.json';self.p.parent.mkdir(parents=True)
  self.p.write_text(json.dumps({'name':'SE02','bed_custom_model':'keep.stl','machine_max_acceleration_x':['500']}))
  self.asset=self.root/'platelink_inmateriis/textures/engineering.png';self.asset.parent.mkdir(parents=True);self.asset.write_bytes(b'asset')
 def tearDown(self):self.tmp.cleanup()
 def test_only_visual_reference_and_backup(self):
  before=self.p.read_bytes();old=json.loads(before)
  self.assertTrue(persist_reference(self.root,self.p,'_subscribed/b/SE02','bed_custom_texture',self.asset,fingerprint(self.p)))
  now=json.loads(self.p.read_text());now.pop('bed_custom_texture');self.assertEqual(now,old)
  self.assertEqual(next((self.root/'platelink_inmateriis/local-reference-backups').glob('*.json')).read_bytes(),before)
 def test_stale_or_wrong_identity_cannot_write(self):
  before=self.p.read_bytes()
  for name,field,digest in [('_subscribed/other/SE02','bed_custom_texture',fingerprint(self.p)),('_subscribed/b/SE02','machine_max_acceleration_x',fingerprint(self.p)),('_subscribed/b/SE02','bed_custom_texture','stale')]:
   with self.assertRaises(ValueError):persist_reference(self.root,self.p,name,field,self.asset,digest)
   self.assertEqual(self.p.read_bytes(),before)
