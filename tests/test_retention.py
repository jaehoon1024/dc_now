import os,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import src19_retention as r
class RetentionTests(unittest.TestCase):
 def test_dry_run_does_not_delete(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/"old.csv";p.write_text("x");ts=(datetime.now(timezone.utc)-timedelta(days=40)).timestamp();os.utime(p,(ts,ts))
   with patch.dict(r.POLICIES,{"exports":(root,30)}):m=r.run("exports")
   self.assertTrue(p.exists());self.assertEqual(m["count"],1);self.assertEqual(m["mode"],"dry-run")
 def test_apply_only_deletes_inside_policy_root(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/"old";p.write_text("x");ts=(datetime.now(timezone.utc)-timedelta(days=40)).timestamp();os.utime(p,(ts,ts))
   with patch.dict(r.POLICIES,{"raw":(root,30)}):r.run("raw",apply=True)
   self.assertFalse(p.exists())
if __name__=="__main__":unittest.main()
