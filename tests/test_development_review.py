import copy,json,os,unittest
from sqlalchemy import create_engine,text
from src28_apply_development_review import DEFAULT,validate_development,apply_development
class DevelopmentReviewTests(unittest.TestCase):
 def test_completion_is_separate_from_unknown_rfs_and_campus_power_is_scoped(self):
  m=validate_development(json.loads(DEFAULT.read_text()));p=m['development_sites'][0]
  self.assertEqual(p['phases'][0]['planned_completion_period'],'2027-06')
  self.assertNotIn('planned_rfs_date',p['phases'][0]);self.assertEqual(p['capacities'][0]['type'],'GRID_INTAKE_MW')
  invalid=copy.deepcopy(m);invalid['development_sites'][0]['capacities'][0]['scope_code']='MISSING'
  with self.assertRaises(ValueError):validate_development(invalid)
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
