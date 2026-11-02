import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
import zlib,struct
from inmateriis_platelink.textures import *

class TexturesTest(unittest.TestCase):
 def test_surfaces_and_unknown(self):
  for surface,key in [('Ingeniería','engineering'),('Fibra de carbono','carbon'),('Vidrio','black-glass'),('PEI texturizado','gold-pei'),('Alta temperatura','high-temperature-metal')]:
   self.assertEqual(texture_for({'surface':surface}),key)
  self.assertIsNone(texture_for({'surface':'PCB Perforada'}))
  self.assertEqual(texture_for({'surface':'Vidrio','texture_id':'carbon'}),'carbon')
 def test_packaged_integrity_and_repair(self):
  with tempfile.TemporaryDirectory() as root:
   for key in TEXTURES:
    p=Path(install_texture(root,key));self.assertTrue(p.read_bytes().startswith(b'\x89PNG'))
    data=p.read_bytes();pos=8;chunks=[]
    while pos<len(data):
     n=struct.unpack('>I',data[pos:pos+4])[0]
     if data[pos+4:pos+8]==b'IDAT':chunks.append(data[pos+8:pos+8+n])
     if data[pos+4:pos+8]==b'IHDR':w,h=struct.unpack('>II',data[pos+8:pos+16])
     pos+=n+12
    raw=zlib.decompress(b''.join(chunks));self.assertEqual({raw[y*(w*4+1)+1+x*4+3] for y in range(h) for x in range(w)},{179})
    p.write_bytes(b'corrupt');install_texture(root,key);self.assertTrue(p.read_bytes().startswith(b'\x89PNG'))
 def test_only_texture_and_stale_guards(self):
  installed={'plate_id':'1','face':'A','texture_id':'carbon'}
  state={'printers':[{'printer':'22IDEX V3','installed':installed}]}
  writes=[];tx=NS(target_name='22IDEX V3',set=lambda *args:writes.append(args),commit=lambda:NS(target_name='22IDEX V3'))
  api=NS(preset=NS(printer=NS(begin_update=lambda:tx)))
  host={'printer':'22IDEX V3','texture':'old','model':'preserve.stl'}
  self.assertTrue(apply_texture(installed,state,host,api,'local.png'))
  self.assertEqual(writes,[('bed_custom_texture','local.png')])
  self.assertFalse(apply_texture(installed,state,{**host,'texture':'local.png'},api,'local.png'))
  tx.target_name='MA01'
  with self.assertRaises(ValueError):apply_texture(installed,state,host,api,'local.png')
  state['printers'][0]['installed']={**installed,'face':'B'}
  with self.assertRaises(ValueError):apply_texture(installed,state,host,api,'local.png')

 def test_explicit_subscribed_alias_and_ambiguous_rejection(self):
  alias='_subscribed/known-bundle/22IDEX V3'
  installed={'plate_id':'1','face':'A','texture_id':'carbon'}
  state={'printers':[{'printer':'22IDEX V3','orca_aliases':[alias],'installed':installed}]}
  self.assertEqual(selected_assignment(state,alias),installed)
  with self.assertRaises(ValueError):selected_assignment(state,'_subscribed/other-bundle/22IDEX V3')
  state['printers'].append({'printer':'Other','orca_aliases':[alias],'installed':installed})
  with self.assertRaises(ValueError):selected_assignment(state,alias)
