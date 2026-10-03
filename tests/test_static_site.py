import json,tempfile,unittest
from pathlib import Path
from src21_build_static_site import write_site
class StaticSiteTests(unittest.TestCase):
 def test_build_writes_public_files_without_secrets(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);write_site({"total":0,"sites":[],"details":{},"regions":[],"companies":[],"yearly":[],"collection_status":[]},out)
   self.assertTrue((out/"index.html").exists());data=(out/"data.json").read_text();self.assertNotIn("password",data.lower());self.assertEqual(json.loads(data)["total"],0)
   headers=(out/"_headers").read_text()
   self.assertNotIn("https://unpkg.com",headers)
   self.assertIn("https://*.tile.openstreetmap.org",headers)
   self.assertTrue((out/"vendor"/"leaflet"/"leaflet.js").exists())
   self.assertIn('src="./vendor/leaflet/leaflet.js"',(out/"index.html").read_text())
   self.assertTrue((out/"app_v3.css").exists())
   self.assertTrue((out/"app_v3.js").exists())
 def test_build_prerenders_public_count_and_rows(self):
  payload={"generated_at":"2026-09-29T00:00:00+09:00","total":1,"target_summary":{"target_total":100,"public_total":1,"needs_evidence_total":99},"sites":[{"site_code":"TEST-001","site_name":"테스트 센터","address_standard":"서울특별시 금천구 가산로 1","sido":"서울특별시","sigungu":"금천구","lifecycle_group":"OPERATING","operating_it_load_mw":None,"review_status":"NEEDS_EVIDENCE","public_visible":False,"latitude":None,"longitude":None,"location_precision":"CITY","discovery_target":True}],"details":{},"regions":[],"companies":[],"yearly":[],"collection_status":[],"evidence_summary":{"total_document_count":491,"public_document_count":480,"confirmed_document_count":491,"source_count":20},"recent_evidence":[{"title":"데이터센터 투자 소식","canonical_url":"https://example.com/evidence","publisher":"테스트신문","published_at":"2026-09-29T00:00:00+09:00","source_grade":"C"}]}
  with tempfile.TemporaryDirectory() as d:
   write_site(payload,Path(d));page=(Path(d)/"index.html").read_text()
   self.assertIn('<strong id="total">100</strong>',page)
   script=(Path(d)/"app_v3.js").read_text()
   self.assertIn('공개 승인 1 · 좌표 확인 0',page)
   self.assertIn('Executive Dashboard',page)
   self.assertIn('Supply Analysis',page)
   self.assertIn('Customer & Demand',page)
   self.assertIn('Data Quality',page)
   self.assertIn('수집 검증 대상',page)
   self.assertIn('근거 확인 필요',page)
   self.assertIn('좌표 확인 필요',page)
   self.assertIn('상세 주소 확인 필요',page)
   self.assertIn('공개 승인',page)
   self.assertIn('근거 491건 · 공개 480건 · 소스 20개',page)
   self.assertIn('데이터센터 투자 소식',page)
   self.assertIn('https://example.com/evidence',page)
   self.assertIn('L.map(id',script)
   self.assertIn('return x.address_standard||',script)
   self.assertIn('encodeURIComponent(mapQuery(x))',script)
   self.assertIn('Available Capacity',page)
   self.assertIn('GPU Ready',page)
   self.assertNotIn("encodeURIComponent(x.latitude+','+x.longitude)",page)
   self.assertIn("테스트 센터",page)
if __name__=="__main__":unittest.main()
