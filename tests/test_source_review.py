import copy,json,os,unittest
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine,text
from src27_apply_source_review import DEFAULT,validate,apply_review
from src26_source_quality_audit import summarize,group

class SourceReviewTests(unittest.TestCase):
 def test_future_dates_and_unclassified_capacity_are_rejected(self):
  m=json.loads(DEFAULT.read_text());validate(m)
  invalid=copy.deepcopy(m);invalid['documents'][0]['published_at']='2099-01-01'
  with self.assertRaises(ValueError):validate(invalid)
  invalid=copy.deepcopy(m);invalid['documents'][0]['capacities'][0]['type']='ANNOUNCED_UNCLASSIFIED_MW'
  with self.assertRaises(ValueError):validate(invalid)
 def test_empty_source_has_no_acquisition_credit(self):
  rows=[dict(source_code='GOOGLE_NEWS_DC',source_type='NEWS',documents=80,aggregator_urls=79),dict(source_code='CBRE_DC_KR',source_type='INDUSTRY',documents=0,aggregator_urls=0)]
  s=summarize(rows);self.assertEqual(s['contributing_sources'],1);self.assertEqual(s['registered_only_sources'],1);self.assertEqual(s['aggregator_share_pct'],98.75)
  self.assertEqual(group(rows[1]),'컨설팅·부동산 리서치')

@unittest.skipUnless(os.getenv('DC_TEST_DATABASE')=='1','rollback-only DB test disabled')
class SourceReviewDatabaseTests(unittest.TestCase):
 def setUp(self):
  from src04_rss_collector import load_env_file,resolve_database_url
  load_env_file();self.engine=create_engine(resolve_database_url());self.addCleanup(self.engine.dispose)
 def test_apply_is_idempotent_on_actual_schema(self):
  m=json.loads(DEFAULT.read_text())
  with self.engine.connect() as c:
   tx=c.begin()
   try:
    counts=apply_review(c,m)
    self.assertTrue(all(n==0 for n in counts.values()),counts)
    counts=apply_review(c,m)
    self.assertTrue(all(n==0 for n in counts.values()),counts)
   finally:tx.rollback()
 def test_hierarchy_excludes_private_unapproved_expired_and_duplicate_values(self):
  with self.engine.connect() as c:
   tx=c.begin()
   try:
    prefix='TEST_'+uuid4().hex[:8]
    site=c.execute(text("INSERT INTO dc_site(site_code,site_name,address_raw,review_status,public_visible) VALUES(:code,'Audit test','test','CONFIRMED',true) RETURNING site_id"),{'code':prefix}).scalar_one()
    source=c.execute(text('SELECT source_id FROM source_registry LIMIT 1')).scalar_one()
    url='https://example.com/'+prefix
    c.execute(text("INSERT INTO evidence_document(source_id,canonical_url,title,document_type,source_grade,access_scope,review_status) VALUES(:s,:u,'Test public','WEB_PAGE','B','PUBLIC','CONFIRMED')"),{'s':source,'u':url})
    def project(suffix,public=True,status='CONFIRMED'):
     return c.execute(text("INSERT INTO dc_project(project_code,site_id,project_name,project_scope,status_code,review_status,public_visible) VALUES(:code,:s,'Test project','test','CONSTRUCTION',:status,:pub) RETURNING project_id"),dict(code=prefix+suffix,s=site,status=status,pub=public)).scalar_one()
    p1=project('_1');p2=project('_2');private=project('_P',False);candidate=project('_C',True,'NEEDS_EVIDENCE')
    ph=c.execute(text("INSERT INTO project_phase(phase_code,project_id,phase_name,scope_description,status_code,review_status) VALUES(:code,:p,'Phase test','test','CONSTRUCTION','CONFIRMED') RETURNING phase_id"),dict(code=prefix+'_PH',p=p2)).scalar_one()
    def capacity(scope,target,mw,stage='DESIGNED',expired=False,excluded=False,doc=url):
     return c.execute(text("INSERT INTO capacity_snapshot(scope_type,scope_id,capacity_type_code,raw_value,raw_unit,normalized_value_mw,capacity_stage,measurement_basis,review_status,document_url,effective_to,aggregation_excluded,exclusion_reason) VALUES(:scope,:target,'IT_LOAD_MW',:mw,'MW',:mw,:stage,'PUBLISHED_CAPACITY','CONFIRMED',:url,CASE WHEN :expired THEN CURRENT_DATE-1 ELSE NULL END,:excluded,'test') RETURNING capacity_id"),dict(scope=scope,target=target,mw=mw,stage=stage,url=doc,expired=expired,excluded=excluded)).scalar_one()
    capacity('PROJECT',p1,10);capacity('PHASE',ph,5)
    capacity('PROJECT',private,900);capacity('PROJECT',candidate,700);capacity('PROJECT',p1,500,expired=True);capacity('PROJECT',p1,400,excluded=True)
    value=lambda:c.execute(text('SELECT development_it_load_mw FROM v_site_map WHERE site_id=:s'),{'s':site}).scalar_one()
    self.assertEqual(value(),15)
    capacity('PROJECT',p2,8);self.assertEqual(value(),18) # parent total replaces its phase, other project retained
    capacity('PROJECT',p1,11,stage='UNDER_CONSTRUCTION');self.assertEqual(value(),19) # latest stage replaces historical design
    capacity('SITE',site,22);self.assertEqual(value(),22) # site total does not add children
    capacity('SITE',site,999,doc='https://example.com/private');self.assertEqual(value(),22) # absent public proof
   finally:tx.rollback()

@unittest.skipUnless(os.getenv('DC_TEST_DATABASE')=='1','rollback-only DB test disabled')
class DiscoveryLinkageTests(unittest.TestCase):
 def test_repeated_public_mentions_raise_gap_until_scope_and_project_are_linked(self):
  from src04_rss_collector import load_env_file,resolve_database_url
  from src26_source_quality_audit import discovery_gaps
  load_env_file();engine=create_engine(resolve_database_url());self.addCleanup(engine.dispose)
  with engine.connect() as c:
   tx=c.begin()
   try:
    code='TEST_'+uuid4().hex[:8];name='테스트팀'+code+'누락'
    sid=c.execute(text("INSERT INTO dc_site(site_code,site_name,address_raw,review_status,public_visible,commercial_scope_status,facility_scope) VALUES(:code,:name,'test','CONFIRMED',true,'REVIEW_REQUIRED','UNKNOWN') RETURNING site_id"),dict(code=code,name=name+' 데이터센터')).scalar_one()
    source=c.execute(text('SELECT source_id FROM source_registry LIMIT 1')).scalar_one()
    for i in range(4):
     c.execute(text("INSERT INTO evidence_document(source_id,canonical_url,title,document_type,source_grade,access_scope,review_status) VALUES(:source,:url,:title,'NEWS','C',:access,'CANDIDATE')"),dict(source=source,url='https://example.com/'+code+str(i),title=name+' 데이터센터 개발',access='PUBLIC' if i<3 else 'INTERNAL'))
    gap=next(x for x in discovery_gaps(c) if x['site_code']==code)
    self.assertEqual(gap['mention_count'],3);self.assertEqual(gap['project_count'],0)
    c.execute(text("UPDATE dc_site SET commercial_scope_status='IN_SCOPE' WHERE site_id=:s"),{'s':sid})
    c.execute(text("INSERT INTO dc_project(project_code,site_id,project_name,project_scope,status_code,review_status,public_visible) VALUES(:code,:s,'linked','test','CONSTRUCTION','CONFIRMED',true)"),{'code':code+'_DEV','s':sid})
    self.assertNotIn(code,[x['site_code'] for x in discovery_gaps(c)])
   finally:tx.rollback()

if __name__=='__main__':unittest.main()
