import os,unittest
from src16_fact_import import REQ,import_rows,validate
class FactImportTests(unittest.TestCase):
 def test_valid_fact_parses_json_and_confidence(self):
  row={"scope_type":"SITE","scope_code":"S1","field_name":"power","value_type":"NUMBER","raw_value_text":"10MW","normalized_value":"10","claim_origin":"PRIMARY","source_grade":"A","confidence_score":"0.9","document_id":"d"}
  rows,e=validate(list(row),[row]);self.assertEqual(e,[]);self.assertEqual(rows[0]["normalized_value"],10)
 def test_invalid_enums_json_and_confidence(self):
  row={k:"x" for k in REQ};row.update(normalized_value="{",confidence_score="2")
  _,e=validate(list(row)+["normalized_value","confidence_score"],[row]);self.assertGreaterEqual(len(e),5)
 @unittest.skipUnless(os.getenv("DC_TEST_DATABASE")=="1","DB test disabled")
 def test_fact_and_evidence_link_are_inserted_as_candidate(self):
  from contextlib import contextmanager
  from sqlalchemy import create_engine,text
  from src04_rss_collector import load_env_file,resolve_database_url
  load_env_file();engine=create_engine(resolve_database_url())
  try:
   with engine.connect() as c:
    tx=c.begin()
    try:
     c.execute(text("CREATE TEMP TABLE company(company_id text PRIMARY KEY) ON COMMIT DROP"));c.execute(text("INSERT INTO company VALUES('ORG-T')"))
     c.execute(text("CREATE TEMP TABLE evidence_document(document_id uuid PRIMARY KEY DEFAULT gen_random_uuid()) ON COMMIT DROP"));doc=c.execute(text("INSERT INTO evidence_document DEFAULT VALUES RETURNING document_id")).scalar()
     c.execute(text("CREATE TEMP TABLE extracted_fact(fact_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),scope_type text,scope_id text,field_name text,value_type text,raw_value_text text,normalized_value jsonb,normalized_unit text,claim_origin text,source_grade text,effective_from date,effective_to date,review_status text,confidence_score numeric) ON COMMIT DROP"))
     c.execute(text("CREATE TEMP TABLE fact_evidence(fact_id uuid,document_id uuid,evidence_location text,quote_text text,is_primary boolean) ON COMMIT DROP"))
     class E:
      @contextmanager
      def begin(self):yield c
     row={"scope_type":"COMPANY","scope_code":"ORG-T","field_name":"name","value_type":"TEXT","raw_value_text":"회사","normalized_value":None,"normalized_unit":"","claim_origin":"PRIMARY","source_grade":"A","effective_from":None,"effective_to":None,"confidence_score":1.0,"document_id":str(doc),"evidence_location":"p1","quote_text":"회사"}
     self.assertEqual(import_rows(E(),[row]),1);self.assertEqual(c.execute(text("SELECT review_status FROM extracted_fact")).scalar(),"CANDIDATE");self.assertTrue(c.execute(text("SELECT is_primary FROM fact_evidence")).scalar())
    finally:tx.rollback()
  finally:engine.dispose()
if __name__=="__main__":unittest.main()
