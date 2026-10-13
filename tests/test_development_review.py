import copy,json,os,unittest
from sqlalchemy import create_engine,text
from src28_apply_development_review import DEFAULT,validate_development,apply_development
from pathlib import Path
OPERATORS=Path(__file__).resolve().parents[1]/'data/reference/kt_sk_review_2026-10-13.json'
class DevelopmentReviewTests(unittest.TestCase):
 def test_completion_is_separate_from_unknown_rfs_and_campus_power_is_scoped(self):
  m=validate_development(json.loads(DEFAULT.read_text()));p=m['development_sites'][0]
  self.assertEqual(p['phases'][0]['planned_completion_period'],'2027-06')
  self.assertNotIn('planned_rfs_date',p['phases'][0]);self.assertEqual(p['capacities'][0]['type'],'GRID_INTAKE_MW')
  invalid=copy.deepcopy(m);invalid['development_sites'][0]['capacities'][0]['scope_code']='MISSING'
  with self.assertRaises(ValueError):validate_development(invalid)
 def test_operator_forecasts_preserve_quarter_year_and_unknown_rfs(self):
  m=validate_development(json.loads(OPERATORS.read_text()));sites={s['site_code']:s for s in m['development_sites']}
  self.assertEqual(sites['SGC_GUNSAN']['phases'][0]['planned_rfs_period'],'2028-Q1')
  self.assertEqual(sites['SK_AWS_ULSAN']['phases'][0]['planned_rfs_period'],'2027')
  self.assertIsNone(sites['SKHORIZON_GURO']['phases'][0]['planned_rfs_period'])
  self.assertEqual(sites['SKHORIZON_GURO']['phases'][0]['planned_completion_period'],'2030')
  invalid=copy.deepcopy(m);invalid['development_sites'][0]['phases'][0]['planned_rfs_period']='2028-Q5'
  with self.assertRaises(ValueError):validate_development(invalid)
 @unittest.skipUnless(os.getenv('DC_TEST_DATABASE')=='1','rollback-only DB test disabled')
 def test_kt_sk_idempotency_scopes_and_unknown_capacity(self):
  from src04_rss_collector import load_env_file,resolve_database_url
  load_env_file();e=create_engine(resolve_database_url());self.addCleanup(e.dispose)
  with e.connect() as c:
   tx=c.begin()
   try:
    counts=apply_development(c,validate_development(json.loads(OPERATORS.read_text())))
    self.assertTrue(all(v==0 for v in counts.values()),counts)
    for code in ['SGC_GUNSAN','SK_AWS_ULSAN','SKHORIZON_GURO']:
     row=c.execute(text('SELECT lifecycle_group,development_it_load_mw,development_grid_intake_mw FROM v_site_map WHERE site_code=:code'),{'code':code}).mappings().one()
     self.assertEqual(row['lifecycle_group'],'DEVELOPMENT');self.assertIsNone(row['development_it_load_mw']);self.assertIsNone(row['development_grid_intake_mw'])
    row=c.execute(text("SELECT lifecycle_group,operating_it_load_mw,operating_grid_intake_mw FROM v_site_map WHERE site_code='KT_GASAN'")).mappings().one()
    self.assertEqual(row['lifecycle_group'],'OPERATING');self.assertEqual(row['operating_it_load_mw'],26);self.assertEqual(row['operating_grid_intake_mw'],40)
    row=c.execute(text("SELECT facility_scope,commercial_scope_status FROM dc_site WHERE site_code='KT_CHEONAN'")).one()
    self.assertEqual(tuple(row),('CLOUD_SELF_USE','OUT_OF_SCOPE'))
    phases={r['phase_code']:r for r in c.execute(text("SELECT phase_code,planned_rfs_period,planned_rfs_date,planned_completion_period FROM project_phase WHERE phase_code IN ('SGC_GUNSAN_PH1','SK_AWS_ULSAN_PH1','SKHORIZON_GURO_PH1')")).mappings()}
    self.assertEqual(phases['SGC_GUNSAN_PH1']['planned_rfs_period'],'2028-Q1');self.assertEqual(phases['SK_AWS_ULSAN_PH1']['planned_rfs_period'],'2027')
    self.assertTrue(all(r['planned_rfs_date'] is None for r in phases.values()));self.assertIsNone(phases['SKHORIZON_GURO_PH1']['planned_rfs_period']);self.assertEqual(phases['SKHORIZON_GURO_PH1']['planned_completion_period'],'2030')
   finally:tx.rollback()
 @unittest.skipUnless(os.getenv('DC_TEST_DATABASE')=='1','rollback-only DB test disabled')
 def test_applied_manifest_is_idempotent_and_schedules_do_not_infer_it_or_rfs(self):
  from src04_rss_collector import load_env_file,resolve_database_url
  load_env_file();e=create_engine(resolve_database_url());self.addCleanup(e.dispose)
  with e.connect() as c:
   tx=c.begin()
   try:
    counts=apply_development(c,json.loads(DEFAULT.read_text()));self.assertTrue(all(v==0 for v in counts.values()),counts)
    row=c.execute(text("select lifecycle_group,development_grid_intake_mw,development_it_load_mw,operating_it_load_mw from v_site_map where site_code='LGU_PAJU'")).mappings().one()
    self.assertEqual(row['lifecycle_group'],'DEVELOPMENT');self.assertEqual(row['development_grid_intake_mw'],200);self.assertIsNone(row['development_it_load_mw']);self.assertIsNone(row['operating_it_load_mw'])
    phase=c.execute(text("select rfs_date,planned_rfs_date,planned_completion_period from project_phase where phase_code='LGU_PAJU_PH1'")).mappings().one()
    self.assertIsNone(phase['rfs_date']);self.assertIsNone(phase['planned_rfs_date']);self.assertEqual(phase['planned_completion_period'],'2027-06')
   finally:tx.rollback()
if __name__=='__main__':unittest.main()
