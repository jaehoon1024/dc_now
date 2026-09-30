import json,tempfile,unittest
from pathlib import Path
from src21_build_static_site import write_site
class StaticSiteTests(unittest.TestCase):
 def test_build_writes_public_files_without_secrets(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);write_site({"total":0,"sites":[],"details":{},"regions":[],"companies":[],"yearly":[],"collection_status":[]},out)
   self.assertTrue((out/"index.html").exists());data=(out/"data.json").read_text();self.assertNotIn("password",data.lower());self.assertEqual(json.loads(data)["total"],0)
   headers=(out/"_headers").read_text()
   self.assertIn("https://unpkg.com",headers)
   self.assertIn("https://*.tile.openstreetmap.org",headers)
 def test_build_prerenders_public_count_and_rows(self):
  payload={"generated_at":"2026-09-29T00:00:00+09:00","total":1,"target_summary":{"target_total":100,"public_total":1,"needs_evidence_total":99},"sites":[{"site_code":"TEST-001","site_name":"테스트 센터","address_standard":"서울특별시 금천구 가산로 1","sido":"서울특별시","sigungu":"금천구","lifecycle_group":"OPERATING","operating_it_load_mw":None,"review_status":"NEEDS_EVIDENCE","public_visible":False,"latitude":None,"longitude":None,"location_precision":"CITY","discovery_target":True}],"details":{},"regions":[],"companies":[],"yearly":[],"collection_status":[]}
  with tempfile.TemporaryDirectory() as d:
   write_site(payload,Path(d));page=(Path(d)/"index.html").read_text()
   self.assertIn('<strong id="total">100</strong>',page)
   self.assertIn('전체 표시 100 · 공개 확정 1',page)
   self.assertIn('수집 검증 대상',page)
   self.assertIn('근거 확인 필요',page)
   self.assertIn('좌표 확인 필요',page)
   self.assertIn('상세 주소 확인 필요',page)
   self.assertIn("L.map('dcmap'",page)
   self.assertNotIn("$('#total').textContent=F.length;",page)
   self.assertIn('query=%EC%84%9C%EC%9A%B8%ED%8A%B9%EB%B3%84%EC%8B%9C+%EA%B8%88%EC%B2%9C%EA%B5%AC+%EA%B0%80%EC%82%B0%EB%A1%9C+1',page)
   self.assertIn('return x.address_standard||',page)
   self.assertIn('encodeURIComponent(mapQuery(x))',page)
   self.assertNotIn("encodeURIComponent(x.latitude+','+x.longitude)",page)
   self.assertIn("테스트 센터",page)
if __name__=="__main__":unittest.main()
