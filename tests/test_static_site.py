import json,tempfile,unittest
from pathlib import Path
from src21_build_static_site import write_site
class StaticSiteTests(unittest.TestCase):
 def test_build_writes_public_files_without_secrets(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);write_site({"total":0,"sites":[],"details":{},"regions":[],"companies":[],"yearly":[],"collection_status":[]},out)
   self.assertTrue((out/"index.html").exists());data=(out/"data.json").read_text();self.assertNotIn("password",data.lower());self.assertEqual(json.loads(data)["total"],0)
if __name__=="__main__":unittest.main()
