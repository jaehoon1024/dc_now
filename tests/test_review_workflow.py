import os,unittest
from src14_review_workflow import ENTITIES,review
class ReviewWorkflowTests(unittest.TestCase):
 def test_all_review_entities_are_configured(self):
  self.assertEqual(set(ENTITIES),{"site","project","company","participation","capacity","evidence","fact"})
 def test_only_public_entities_can_be_published(self):
  self.assertEqual({k for k,v in ENTITIES.items() if v.public_column},{"site","project","participation"})
 def test_evidence_and_fact_record_reviewer(self):
  self.assertTrue(ENTITIES["evidence"].reviewer_columns);self.assertTrue(ENTITIES["fact"].reviewer_columns)
 def test_evidence_queue_exposes_review_context(self):
  self.assertTrue({"canonical_url","publisher","published_at","source_grade"}<=set(ENTITIES["evidence"].detail_columns))
 def test_blank_reviewer_or_note_is_rejected(self):
  with self.assertRaises(ValueError):review(None,"evidence","x","approve","","note")
  with self.assertRaises(ValueError):review(None,"evidence","x","approve","tester"," ")
 @unittest.skipUnless(os.getenv("DC_TEST_DATABASE")=="1","DB test disabled")
 def test_review_updates_status_and_writes_audit(self):
  from contextlib import contextmanager
  from sqlalchemy import create_engine,text
  from src04_rss_collector import load_env_file,resolve_database_url
  load_env_file();engine=create_engine(resolve_database_url())
  try:
   with engine.connect() as c:
    tx=c.begin()
    try:
     c.execute(text("CREATE TEMP TABLE company(company_id text PRIMARY KEY,standard_name text,review_status text,updated_at timestamptz DEFAULT now()) ON COMMIT DROP"))
     c.execute(text("CREATE TEMP TABLE audit_log(actor_id text,role_at_action text,action text,entity_type text,entity_id text,before_value jsonb,after_value jsonb,reason text,result text) ON COMMIT DROP"))
     c.execute(text("INSERT INTO company VALUES('ORG-T','테스트','CANDIDATE',now())"))
     class E:
      @contextmanager
      def begin(self):yield c
     review(E(),"company","ORG-T","approve","tester","근거 확인")
     self.assertEqual(c.execute(text("SELECT review_status FROM company")).scalar(),"CONFIRMED")
     self.assertEqual(c.execute(text("SELECT result FROM audit_log")).scalar(),"SUCCESS")
    finally:tx.rollback()
  finally:engine.dispose()
if __name__=="__main__":unittest.main()
