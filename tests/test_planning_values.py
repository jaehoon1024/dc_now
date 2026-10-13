import copy,io,json,os,unittest
from uuid import uuid4
from contextlib import contextmanager
from planning_values import validate_value,write_value,list_values,PlanningConflict

def value(code,**changes):
 return dict(site_code=code,scope_type='SITE',scope_code=code,field_name='IT_LOAD_MW',bucket='OPERATING',value=10,low_value=5,high_value=15,basis='ESTIMATED',method='test planning assumption',source_url=None,public_visible=True,active=True,expected_version=0,reviewer='planning-test',**changes)

class ValidationTests(unittest.TestCase):
 def test_zero_capacity_is_a_value_and_invalid_inputs_are_rejected(self):
  d=value('TEST_A');d.update(value=0,low_value=0);validate_value(d)
  for patch in [{'value':-1},{'value':True},{'value':float('nan')},{'high_value':3},{'scope_code':'../file'},{'expected_version':True},{'basis':'CONFIRMED'},{'source_url':'https://example.com/?api_key=secret'},{'source_url':123},{'public_visible':'true'}]:
   with self.subTest(patch=patch),self.assertRaises(ValueError):validate_value({**value('TEST_A'),**patch})
 def test_periods_are_real_dates_and_preserve_precision(self):
  d=value('TEST_A');d.update(field_name='RFS_PERIOD',bucket='GENERAL',low_value=None,high_value=None)
  for period in ['2028','2028-Q2','2028 q2','2028-06','2028-02-29']:validate_value({**d,'value':period})
  self.assertEqual(validate_value({**d,'value':'2028 q2'})['value'],'2028-Q2')
  for period in ['2027-02-29','2028-13','2028-Q5','0000','next year']:
   with self.subTest(period=period),self.assertRaises(ValueError):validate_value({**d,'value':period})
  status={**d,'field_name':'STATUS_CODE','value':'CONSTRUCTION'}
  with self.assertRaises(ValueError):validate_value(status)
  validate_value({**status,'scope_type':'PROJECT','scope_code':'TEST_PROJECT'})

@unittest.skipUnless(os.getenv('DC_TEST_DATABASE')=='1','rollback-only DB tests disabled')
class PlanningDatabaseTests(unittest.TestCase):
 def setUp(self):
  from sqlalchemy import create_engine,text
  from src04_rss_collector import load_env_file,resolve_database_url
  load_env_file();self.engine=create_engine(resolve_database_url());self.addCleanup(self.engine.dispose);self.text=text
 def test_versions_audit_retirement_and_private_values(self):
  with self.engine.connect() as c:
   tx=c.begin()
   try:
    code='TEST_'+uuid4().hex[:8].upper();c.execute(self.text("INSERT INTO dc_site(site_code,site_name,address_raw,review_status,public_visible) VALUES(:code,'Test','test','CONFIRMED',true)"),{'code':code})
    row=write_value(c,value(code));self.assertEqual(row['version'],1)
    with self.assertRaises(PlanningConflict):write_value(c,value(code))
    class Bound:
     @contextmanager
     def connect(self):yield c
    self.assertEqual(list_values(Bound(),site_code=code)[0]['value'],10)
    d=value(code);d.update(value=12,expected_version=1,public_visible=False)
    row=write_value(c,d);self.assertEqual(row['version'],2);self.assertEqual(list_values(Bound(),site_code=code),[])
    self.assertEqual(list_values(Bound(),False,code)[0]['value'],12)
    d.update(expected_version=2,active=False,public_visible=True);write_value(c,d);self.assertEqual(list_values(Bound(),site_code=code),[])
    count=c.execute(self.text("SELECT count(*) FROM audit_log WHERE entity_type='PLANNING_VALUE' AND entity_id=:id"),{'id':str(row['planning_id'])}).scalar_one();self.assertEqual(count,3)
   finally:tx.rollback()
 def test_scope_must_belong_to_site_and_private_projects_do_not_publish(self):
  with self.engine.connect() as c:
   tx=c.begin()
   try:
    code='TEST_'+uuid4().hex[:8].upper();sid=c.execute(self.text("INSERT INTO dc_site(site_code,site_name,address_raw,review_status,public_visible) VALUES(:code,'Test','test','CONFIRMED',true) RETURNING site_id"),{'code':code}).scalar_one()
    pcode=code+'_P';c.execute(self.text("INSERT INTO dc_project(project_code,site_id,project_name,project_scope,status_code,review_status,public_visible) VALUES(:code,:site,'Private','test','CONSTRUCTION','CONFIRMED',false)"),{'code':pcode,'site':sid})
    d=value(code);d.update(scope_type='PROJECT',scope_code=pcode,bucket='DEVELOPMENT');write_value(c,d)
    class Bound:
     @contextmanager
     def connect(self):yield c
    self.assertEqual(list_values(Bound(),site_code=code),[]);self.assertEqual(len(list_values(Bound(),False,code)),1)
    with self.assertRaises(ValueError):write_value(c,{**d,'scope_code':'MISSING_PROJECT'})
   finally:tx.rollback()
 def test_import_failure_rolls_back_all_items(self):
  from internal_api import make_app
  with self.engine.connect() as c:
   tx=c.begin()
   try:
    code='TEST_'+uuid4().hex[:8].upper();c.execute(self.text("INSERT INTO dc_site(site_code,site_name,address_raw,review_status,public_visible) VALUES(:code,'Test','test','CONFIRMED',true)"),{'code':code})
    class Bound:
     @contextmanager
     def begin(self):
      with c.begin_nested():yield c
    app=make_app(Bound(),'x'*32);got={};d=value(code);other={**d,'scope_type':'PROJECT','scope_code':'MISSING'};payload=json.dumps({'items':[d,other],'reviewer':'test'}).encode()
    b=b''.join(app({'REQUEST_METHOD':'POST','PATH_INFO':'/internal/v1/planning-import','HTTP_AUTHORIZATION':'Bearer '+'x'*32,'CONTENT_LENGTH':str(len(payload)),'wsgi.input':io.BytesIO(payload)},lambda status,headers:got.update(status=status)))
    self.assertEqual(got['status'],'400 Bad Request');self.assertEqual(c.execute(self.text("SELECT count(*) FROM planning_value pv JOIN dc_site s USING(site_id) WHERE s.site_code=:code"),{'code':code}).scalar_one(),0)
   finally:tx.rollback()

if __name__=='__main__':unittest.main()
