import json
import tempfile
import unittest
from pathlib import Path
from src21_build_static_site import write_site


class StaticSiteTests(unittest.TestCase):
 def test_planning_identifiers_and_ranges_serialize_in_real_snapshot(self):
  from uuid import uuid4
  from decimal import Decimal
  uid=uuid4();payload={'total':0,'sites':[],'planning_values':[{'planning_id':uid,'value':40,'low_value':Decimal('35.000'),'high_value':Decimal('45.000')}]}
  with tempfile.TemporaryDirectory() as d:
   write_site(payload,Path(d));row=json.loads((Path(d)/'data.json').read_text())['planning_values'][0]
   self.assertEqual(row['planning_id'],str(uid));self.assertEqual(row['low_value'],35)
 def test_build_writes_public_files_without_secrets(self):
  payload={"total":0,"sites":[],"details":{},"companies":[],"collection_status":[]}
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);write_site(payload,out)
   self.assertEqual(json.loads((out/"data.json").read_text())["total"],0)
   page=(out/"index.html").read_text()
   self.assertIn('data-mode="public"',page)
   self.assertRegex(page,r'manager-core\.js\?v=[a-f0-9]{12}')
   self.assertNotIn('data-mode="internal"',page)
   for name in ('manager.css','manager-core.js','manager.js','.nojekyll'):
    self.assertTrue((out/name).exists())
   self.assertNotIn('password', (out/"data.json").read_text().lower())
   self.assertIn('https://maps.google.com',(out/"_headers").read_text())
   self.assertNotIn('review_queue', (out/"data.json").read_text())

 def test_prerender_survives_script_loading_failure_and_escapes_site_name(self):
  payload={"total":1,"target_summary":{"commercial_confirmed_total":1,"needs_evidence_total":2},"evidence_summary":{"public_document_count":12},"sites":[{"site_name":"센터 <script>alert(1)</script>","sido":"서울","lifecycle_group":"OPERATING","facility_scope":"COMMERCIAL"}],"details":{}}
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);write_site(payload,out);page=(out/"index.html").read_text()
   self.assertIn('<strong id="initialTotal">1</strong>',page)
   self.assertIn('<strong id="initialCommercial">1</strong>',page)
   self.assertIn('<strong id="initialEvidence">12</strong>',page)
   self.assertIn('센터 &lt;script&gt;',page)
   self.assertNotIn('<script>alert(1)</script>',page)
   for label in ('오늘의 업무','센터 현황','개발 프로젝트','공급 분석','근거 검토','수집·발행'):
    self.assertIn(label,page)
