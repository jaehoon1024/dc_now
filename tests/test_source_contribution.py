import unittest
from source_contribution import diagnose
from official_collection import metadata,check_source,CollectionIssue

class ContributionTests(unittest.TestCase):
 def test_registration_is_not_connection(self):
  row={'source_code':'API','active':True,'collection_method':'API','documents':0}
  self.assertEqual(diagnose(row)[0],'API_NOT_CONNECTED')
  row.update(collection_method='MANUAL',documents=1)
  self.assertEqual(diagnose(row)[0],'MANUAL')
  row.update(configured_routes=1)
  self.assertEqual(diagnose(row)[0],'NOT_RUN')
  row.update(latest_success_at='2026-10-16')
  self.assertEqual(diagnose(row)[0],'CONNECTED')
 def test_failed_route_is_not_healthy_because_it_has_old_documents(self):
  row={'source_code':'A','active':True,'documents':10,'configured_routes':1,'latest_success_at':'2026-10-01'}
  self.assertEqual(diagnose(row,{'status':'FAILED','error_code':'HTTP_403'})[0],'FAILED')
  row['failing_routes']=1;self.assertEqual(diagnose(row)[0],'FAILED')
 def test_contract_and_disabled(self):
  self.assertEqual(diagnose({'source_code':'A_LICENSED'})[0],'CONTRACT_REQUIRED')
  self.assertEqual(diagnose({'source_code':'A','active':False})[0],'INACTIVE')
 def test_metadata_retains_no_body_and_no_script_only_relevance(self):
  doc=metadata('<title>센터 안내</title><h1>데이터센터</h1><p>본문을 저장하지 않습니다</p>','https://example.com/')
  self.assertEqual(doc['title'],'센터 안내');self.assertNotIn('본문',str(doc));self.assertIsNone(doc['published_at'])
  with self.assertRaises(CollectionIssue):metadata('<title>Other</title><script>data center</script>','https://example.com/')
 def test_robots_and_html_shells_are_not_successful_collection(self):
  def blocked(url):return ('User-agent: *\nDisallow: /','text/plain')
  with self.assertRaisesRegex(CollectionIssue,'ROBOTS_DISALLOWED'):check_source({'url':'https://example.com/'},blocked)
  def html_robots(url):return ('<html>home</html>','text/html')
  with self.assertRaisesRegex(CollectionIssue,'ROBOTS_REVIEW_REQUIRED'):check_source({'url':'https://example.com/'},html_robots)
 def test_allowed_page_gets_metadata_only(self):
  def allowed(url):return ('User-agent: *\nAllow: /','text/plain') if url.endswith('robots.txt') else ('<title>공식 DC</title><p>데이터센터</p>','text/html')
  item,state=check_source({'url':'https://example.com/center'},allowed)
  self.assertEqual(item['canonical_url'],'https://example.com/center');self.assertEqual(state,'ALLOWED')

class RedirectTests(unittest.TestCase):
 def test_only_reviewed_exact_https_redirect_is_allowed(self):
  from official_collection import SameHost
  from urllib.request import Request
  request=Request('https://idc.example.com/robots.txt')
  with self.assertRaises(CollectionIssue):SameHost().redirect_request(request,None,302,'',{},'https://example.com/error/404')
  handler=SameHost(['https://example.com/error/404'])
  self.assertIsNotNone(handler.redirect_request(request,None,302,'',{},'https://example.com/error/404'))
  for url in ['https://example.com/other','http://idc.example.com/robots.txt']:
   with self.assertRaises(CollectionIssue):handler.redirect_request(request,None,302,'',{},url)

class CollectionPolicyTests(unittest.TestCase):
 def test_existing_request_interval_is_honored(self):
  slept=[]
  def fetch(url):return ('User-agent: *\nAllow: /','text/plain') if url.endswith('robots.txt') else ('<title>DC</title><p>데이터센터</p>','text/html')
  check_source({'url':'https://example.com/','request_interval_seconds':30},fetch,slept.append)
  self.assertEqual(slept,[30])
 def test_daily_newsroom_defaults_to_six_pages(self):
  from unittest.mock import patch
  from src05_newsroom_collector import parse_args
  with patch('sys.argv',['collector']):self.assertEqual(parse_args().max_pages,6)
