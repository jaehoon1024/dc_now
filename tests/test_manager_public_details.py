import os
import unittest
from contextlib import contextmanager
from uuid import uuid4


@unittest.skipUnless(os.getenv('DC_TEST_DATABASE') == '1', 'rollback-only DB test disabled')
class ManagerPublicDetailTests(unittest.TestCase):
    def test_unapproved_phases_private_projects_and_private_sources_are_omitted(self):
        from sqlalchemy import create_engine, text
        from public_api import PublicRepository
        from src04_rss_collector import load_env_file, resolve_database_url
        load_env_file()
        engine = create_engine(resolve_database_url())
        self.addCleanup(engine.dispose)
        prefix = 'TEST_' + uuid4().hex[:8]
        with engine.connect() as c:
            tx = c.begin()
            try:
                chosen = c.execute(text("SELECT site_id,site_code FROM dc_site WHERE public_visible AND review_status='CONFIRMED' AND commercial_scope_status='IN_SCOPE' AND commercial_review_status='CONFIRMED' LIMIT 1")).mappings().one()
                source = c.execute(text('SELECT source_id FROM source_registry LIMIT 1')).scalar_one()
                url = 'https://example.com/' + prefix
                c.execute(text("INSERT INTO evidence_document(source_id,canonical_url,title,document_type,source_grade,access_scope,review_status) VALUES(:source,:url,'Private test','NEWS','C','INTERNAL','CONFIRMED')"), {'source':source,'url':url})
                c.execute(text("INSERT INTO capacity_snapshot(scope_type,scope_id,capacity_type_code,raw_value,raw_unit,normalized_value_mw,capacity_stage,measurement_basis,document_url,review_status) VALUES('SITE',:site,'IT_LOAD_MW','20','MW',20,'OPERATING','PUBLISHED_CAPACITY',:url,'CONFIRMED')"), {'site':chosen['site_id'],'url':url})
                codes = []
                for public in (True, False):
                    code=prefix+('_PUB' if public else '_PRIV');codes.append(code)
                    project=c.execute(text("INSERT INTO dc_project(project_code,site_id,project_name,project_scope,status_code,review_status,public_visible) VALUES(:code,:site,'Test project','test','IDEA','CONFIRMED',:public) RETURNING project_id"), {'code':code,'site':chosen['site_id'],'public':public}).scalar_one()
                    for confirmed in (True,False):
                        phcode=code+('_OK' if confirmed else '_WAIT')
                        c.execute(text("INSERT INTO project_phase(phase_code,project_id,phase_name,scope_description,status_code,review_status) VALUES(:code,:pid,'Test phase','test','IDEA',:status)"), {'code':phcode,'pid':project,'status':'CONFIRMED' if confirmed else 'NEEDS_EVIDENCE'})
                class Bound:
                    @contextmanager
                    def connect(self):
                        yield c
                result = PublicRepository(Bound()).site_detail(chosen['site_code'])
                self.assertIn(codes[0], [x['project_code'] for x in result['projects']])
                self.assertNotIn(codes[1], [x['project_code'] for x in result['projects']])
                phases=[x['phase_code'] for x in result['phases']]
                self.assertIn(codes[0]+'_OK', phases)
                self.assertNotIn(codes[0]+'_WAIT', phases)
                self.assertNotIn(codes[1]+'_OK', phases)
                self.assertNotIn(url, [x['document_url'] for x in result['capacities']])
            finally:
                tx.rollback()
        engine.dispose()
