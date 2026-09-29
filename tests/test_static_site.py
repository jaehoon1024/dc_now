import json,tempfile,unittest
from pathlib import Path
from src21_build_static_site import write_site
class StaticSiteTests(unittest.TestCase):
 def test_build_writes_public_files_without_secrets(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);write_site({"total":0,"sites":[],"details":{},"regions":[],"companies":[],"yearly":[],"collection_status":[]},out)
   self.assertTrue((out/"index.html").exists());data=(out/"data.json").read_text();self.assertNotIn("password",data.lower());self.assertEqual(json.loads(data)["total"],0)
 def test_build_prerenders_public_count_and_rows(self):
  payload={"generated_at":"2026-09-29T00:00:00+09:00","total":1,"sites":[{"site_name":"테스트 센터","sido":"서울특별시","sigungu":"금천구","lifecycle_group":"OPERATING","operating_it_load_mw":None}],"details":{},"regions":[],"companies":[],"yearly":[],"collection_status":[]}
  with tempfile.TemporaryDirectory() as d:
   write_site(payload,Path(d));page=(Path(d)/"index.html").read_text()
   self.assertIn('<strong id="total">1</strong>',page)
   self.assertIn("테스트 센터",page)
if __name__=="__main__":unittest.main()
