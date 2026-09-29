import os, unittest
from src13_reference_import import FIELDS, import_rows, validate

class ReferenceImportTests(unittest.TestCase):
 def test_company_rejects_bad_url(self):
  _,e=validate("company",list(FIELDS["company"]),[{"company_id":"ORG-100","standard_name":"회사","official_url":"javascript:x"}]);self.assertTrue(e)
 def test_participation_validates_role_and_confidence(self):
  _,e=validate("participation",list(FIELDS["participation"]),[{"company_id":"ORG-001","scope_type":"SITE","scope_code":"SITE-1","role_code":"BAD","confidence_score":"2"}]);self.assertEqual(len(e),2)
 def test_capacity_requires_positive_value(self):
  row={"scope_type":"SITE","scope_code":"SITE-1","capacity_type_code":"IT_LOAD_MW","raw_value":"-1","raw_unit":"MW","normalized_value_mw":"-1","capacity_stage":"OPERATING","measurement_basis":"NAMEPLATE"}
  _,e=validate("capacity",list(FIELDS["capacity"]),[row]);self.assertIn("양수 숫자 필요",[x[2] for x in e])
 def test_evidence_validates_type_and_timestamp(self):
  row={"source_code":"SRC","title":"문서","document_type":"BAD","source_grade":"A","published_at":"today"}
  _,e=validate("evidence",list(FIELDS["evidence"]),[row]);self.assertEqual(len(e),2)
 def test_valid_rows_remain_candidate_inputs(self):
  cases={
   "company":{"company_id":"ORG-100","standard_name":"회사"},
   "participation":{"company_id":"ORG-001","scope_type":"SITE","scope_code":"SITE-1","role_code":"OWNER"},
   "capacity":{"scope_type":"SITE","scope_code":"SITE-1","capacity_type_code":"IT_LOAD_MW","raw_value":"10","raw_unit":"MW","capacity_stage":"OPERATING","measurement_basis":"NAMEPLATE"},
   "evidence":{"source_code":"SRC","title":"문서","document_type":"PDF","source_grade":"A"},
  }
  for kind,row in cases.items():self.assertEqual(validate(kind,list(FIELDS[kind]),[row])[1],[])
 @unittest.skipUnless(os.getenv("DC_TEST_DATABASE")=="1","DB test disabled")
 def test_all_imports_apply_restricted_defaults(self):
  from contextlib import contextmanager
  from sqlalchemy import create_engine,text
  from src04_rss_collector import load_env_file,resolve_database_url
  load_env_file();engine=create_engine(resolve_database_url())
  try:
   with engine.connect() as c:
    tx=c.begin()
    try:
     statements=[
      "CREATE TEMP TABLE company(company_id text PRIMARY KEY,standard_name text,legal_name text,business_registration_no text,official_url text,review_status text,note text) ON COMMIT DROP",
      "CREATE TEMP TABLE dc_site(site_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),site_code text UNIQUE) ON COMMIT DROP",
      "CREATE TEMP TABLE company_participation(company_id text,scope_type text,scope_id uuid,role_code text,valid_from date,valid_to date,review_status text,confidence_score numeric,evidence_url text,public_visible boolean,note text) ON COMMIT DROP",
      "CREATE TEMP TABLE capacity_snapshot(scope_type text,scope_id uuid,capacity_type_code text,raw_value text,raw_unit text,normalized_value_mw numeric,normalized_value numeric,normalized_unit text,capacity_stage text,measurement_basis text,effective_from date,effective_to date,document_url text,evidence_location text,review_status text,note text) ON COMMIT DROP",
      "CREATE TEMP TABLE source_registry(source_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),source_code text UNIQUE) ON COMMIT DROP",
      "CREATE TEMP TABLE evidence_document(source_id uuid,canonical_url text,external_document_id text,title text,document_type text,publisher text,published_at timestamptz,source_grade text,access_scope text) ON COMMIT DROP",
     ]
     for sql in statements:c.execute(text(sql))
     c.execute(text("INSERT INTO dc_site(site_code) VALUES('SITE-1')"));c.execute(text("INSERT INTO source_registry(source_code) VALUES('SRC')"))
     class E:
      @contextmanager
      def begin(self):yield c
     samples={
      "company":{"company_id":"ORG-100","standard_name":"회사","legal_name":"","business_registration_no":"","official_url":"","note":""},
      "participation":{"company_id":"ORG-100","scope_type":"SITE","scope_code":"SITE-1","role_code":"OWNER","valid_from":None,"valid_to":None,"confidence_score":None,"evidence_url":"","note":""},
      "capacity":{"scope_type":"SITE","scope_code":"SITE-1","capacity_type_code":"IT_LOAD_MW","raw_value":"10","raw_unit":"MW","normalized_value_mw":10.0,"normalized_value":10.0,"normalized_unit":"MW","capacity_stage":"OPERATING","measurement_basis":"NAMEPLATE","effective_from":None,"effective_to":None,"document_url":"","evidence_location":"","note":""},
      "evidence":{"source_code":"SRC","canonical_url":"","external_document_id":"","title":"문서","document_type":"PDF","publisher":"","published_at":None,"source_grade":"A"},
     }
     for kind,row in samples.items():self.assertEqual(import_rows(E(),kind,[row]),1)
     self.assertEqual(c.execute(text("SELECT review_status FROM company")).scalar(),"CANDIDATE")
     self.assertEqual(c.execute(text("SELECT review_status||':'||public_visible FROM company_participation")).scalar(),"CANDIDATE:false")
     self.assertEqual(c.execute(text("SELECT review_status FROM capacity_snapshot")).scalar(),"CANDIDATE")
     self.assertEqual(c.execute(text("SELECT access_scope FROM evidence_document")).scalar(),"INTERNAL")
    finally:tx.rollback()
  finally:engine.dispose()
if __name__=="__main__":unittest.main()
