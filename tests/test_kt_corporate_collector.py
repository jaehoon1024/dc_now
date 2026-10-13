import json,unittest
from datetime import date
from src05_newsroom_collector import parse_kt_corporate,article_batches,CollectorError

class KtCorporateTests(unittest.TestCase):
 def response(self,number,pages,day='2026-09-28'):
  return json.dumps({'code':'200','body':[{'seq':'20260929084129950','title':'kt cloud &#39;군산&#39; 데이터센터','openYn':'Y','pressDateNm':day+' 00:00:00','contentsText':'ARTICLE BODY MUST NOT BE STORED','instUser':'admin'}],'pagination':{'curPage':number,'pageCnt':pages}}).encode()
 def page(self):return {'parser_code':'KT_CORP_JSON_V1','page_url':'https://data.ktcloud.com/api/board/list/media/press/kor?curPage=1&pageSize=9&source=dc','request_interval_seconds':30}
 def test_publication_date_does_not_come_from_url_and_article_text_is_discarded(self):
  item=parse_kt_corporate(self.response(1,2))[0]
  self.assertEqual(item['published_at'].date(),date(2026,9,28))
  self.assertEqual(item['canonical_url'],'https://www.ktcloud.com/media/press/20260929084129950?lan=kor')
  self.assertNotIn('ARTICLE BODY',json.dumps(item,default=str));self.assertNotIn('instUser',item)
 def test_pagination_keeps_filter_and_stops_at_date_boundary(self):
  page=self.page();requests=[];waits=[]
  def fetch(p):
   requests.append(p['page_url']);return self.response(len(requests),3,'2026-09-28' if len(requests)==1 else '2023-09-12')
  batches=list(article_batches(page,3,date(2023,10,13),fetch,waits.append))
  self.assertEqual([len(x) for x in batches],[1,0]);self.assertEqual(page['scan_end'],'date_limit')
  self.assertIn('source=dc',requests[1]);self.assertIn('curPage=2',requests[1]);self.assertEqual(waits,[30])
 def test_mismatched_page_and_external_host_are_rejected(self):
  for page,response in [(self.page(),self.response(2,3)),({**self.page(),'page_url':'https://example.com/'},self.response(1,3))]:
   with self.assertRaises(CollectorError):list(article_batches(page,3,fetch=lambda p:response,sleep=lambda n:None))

if __name__=='__main__':unittest.main()
