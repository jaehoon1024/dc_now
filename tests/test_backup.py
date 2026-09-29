import os,tempfile,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from src17_backup import retention_candidates,sha256
class BackupTests(unittest.TestCase):
 def test_checksum_is_stable(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"x";p.write_bytes(b"abc");self.assertEqual(sha256(p),"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
 def test_retention_only_selects_named_old_dumps(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);old=root/"dc_platform_old.dump";old.write_bytes(b"x");other=root/"other.dump";other.write_bytes(b"x");ts=(datetime.now(timezone.utc)-timedelta(days=40)).timestamp();os.utime(old,(ts,ts));self.assertEqual(retention_candidates(30,root),[old])
if __name__=="__main__":unittest.main()
