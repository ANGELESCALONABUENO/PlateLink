import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from inmateriis_platelink.apply import apply_installed_bed,sync_installed_bed
class ApplyTests(unittest.TestCase):
    def test_stale_or_unmapped_plate_does_not_change_the_project(self):
        calls=[]
        api=SimpleNamespace(preset=SimpleNamespace(project=SimpleNamespace(select_bed_type=lambda **kw:calls.append(kw) or kw["bed_type"])))
        host={"printer":"MA01","bed_type":"High Temp Plate"}
        expected={"plate_id":"eng1","face":"A","bed_type":"Engineering Plate"}
        fresh={"review":{"installed":expected}}
        self.assertEqual(apply_installed_bed(expected,fresh,host,api),"Engineering Plate")
        self.assertEqual(calls,[dict(bed_type="Engineering Plate",expected_printer="MA01",expected_current="High Temp Plate")])
        for wrong in [None,{**expected,"face":"B"},{**expected,"plate_id":"eng2"}]:
            with self.assertRaises(ValueError):apply_installed_bed(expected,{"review":{"installed":wrong}},host,api)
        unknown={**expected,"bed_type":None}
        with self.assertRaises(ValueError):apply_installed_bed(unknown,{"review":{"installed":unknown}},host,api)
        self.assertEqual(len(calls),1)
    def test_native_refresh_selects_installed_bed_but_skips_dashboard_and_noops(self):
        calls=[]
        api=SimpleNamespace(preset=SimpleNamespace(project=SimpleNamespace(select_bed_type=lambda **kw:calls.append(kw) or kw["bed_type"])))
        host={"printer":"SE02","bed_type":"High Temp Plate","can_select_bed":True}
        installed={"plate_id":"pei1","face":"A","bed_type":"Textured PEI Plate"}
        state={"review":{"installed":installed}}
        self.assertEqual(sync_installed_bed(state,host,api),"Textured PEI Plate")
        for snapshot in [{**host,"can_select_bed":False},{**host,"bed_type":"Textured PEI Plate"}]:
            self.assertIsNone(sync_installed_bed(state,snapshot,api))
        self.assertIsNone(sync_installed_bed({"review":{"installed":None}},host,api))
        self.assertIsNone(sync_installed_bed({"review":{"installed":{**installed,"bed_type":None}}},host,api))
        self.assertEqual(len(calls),1)

if __name__=="__main__":unittest.main()
