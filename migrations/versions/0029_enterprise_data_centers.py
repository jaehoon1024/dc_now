"""Track enterprise and self-use cloud data centers separately.

Revision ID: 0029_enterprise_data_centers
Revises: 0028_player_relationships
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_enterprise_data_centers"
down_revision: Union[str, None] = "0028_player_relationships"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("dc_site", sa.Column("facility_scope", sa.String(30), nullable=False, server_default=sa.text("'UNKNOWN'")))
    op.add_column("dc_site", sa.Column("facility_review_status", sa.String(30), nullable=False, server_default=sa.text("'NEEDS_EVIDENCE'")))
    op.add_column("dc_site", sa.Column("facility_scope_note", sa.Text(), nullable=True))
    op.add_column("dc_site", sa.Column("facility_source_url", sa.String(2000), nullable=True))
    op.create_check_constraint("ck_dc_site_facility_scope", "dc_site", "facility_scope IN ('COMMERCIAL','ENTERPRISE','CLOUD_SELF_USE','PUBLIC','UNKNOWN')")
    op.create_check_constraint("ck_dc_site_facility_review", "dc_site", "facility_review_status IN ('CONFIRMED','NEEDS_EVIDENCE')")
    op.create_index("idx_dc_site_facility_scope", "dc_site", ["facility_scope", "facility_review_status"])
    op.execute("""
      UPDATE dc_site SET facility_scope='COMMERCIAL',facility_review_status='CONFIRMED',
        facility_scope_note='상용 데이터센터 범위에서 검토 완료',facility_source_url=commercial_source_url
      WHERE commercial_scope_status='IN_SCOPE' AND commercial_review_status='CONFIRMED'
    """)
    op.execute("""
      INSERT INTO company(company_id,standard_name,legal_name,official_url,review_status,note) VALUES
        ('COMP_HYUNDAI_MOTOR','현대자동차','현대자동차 주식회사','https://www.hyundai.com/kr/ko/','CONFIRMED','기업 전용 IT센터 추적'),
        ('COMP_SAMSUNG_ELEC','삼성전자','삼성전자 주식회사','https://www.samsung.com/sec/','CONFIRMED','기업 전용 IT센터 추적'),
        ('COMP_SK_HYNIX','SK하이닉스','에스케이하이닉스 주식회사','https://www.skhynix.com/','CONFIRMED','기업 전용 IT센터 추적')
      ON CONFLICT(company_id) DO NOTHING
    """)
    op.execute("""
      INSERT INTO source_feed(source_id,feed_code,feed_name,feed_url,feed_format,filter_mode,
        filter_keywords,storage_policy,request_interval_seconds,active,note)
      SELECT source_id,'GNEWS_ENTERPRISE_DC','기업 전용 데이터센터',
        'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%ED%98%84%EB%8C%80%EC%9E%90%EB%8F%99%EC%B0%A8+OR+%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90+OR+SK%ED%95%98%EC%9D%B4%EB%8B%89%EC%8A%A4+OR+%EB%84%A4%EC%9D%B4%EB%B2%84+OR+%EC%B9%B4%EC%B9%B4%EC%98%A4+OR+LG+CNS%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako',
        'RSS','ALL','[]'::jsonb,'METADATA_ONLY',15,true,
        '기업 전용·클라우드 자체·IT서비스사 데이터센터 제목·URL·게시일 탐색'
      FROM source_registry WHERE source_code='GOOGLE_NEWS_DC'
      ON CONFLICT(feed_url) DO UPDATE SET active=true,updated_at=CURRENT_TIMESTAMP
    """)
    op.execute("""
      INSERT INTO dc_site(site_code,site_name,site_name_raw,address_raw,address_standard,sido,
        review_status,public_visible,commercial_scope_status,commercial_model,
        commercial_review_status,commercial_scope_note,commercial_source_url,
        facility_scope,facility_review_status,facility_scope_note,facility_source_url)
      VALUES ('LGCNS_INCHEON','LG CNS 인천 데이터센터','LG CNS 인천센터','인천광역시',
        '인천광역시','인천광역시','CONFIRMED',true,'IN_SCOPE','MANAGED_SERVICE','CONFIRMED',
        'LG CNS 공식 센터 목록과 데이터센터 서비스 확인',
        'https://www.lgcns.com/kr/service/modern-it-infra-on-cloud/data-center',
        'COMMERCIAL','CONFIRMED','LG CNS 자체 운영 데이터센터',
        'https://www.lgcns.com/kr/service/modern-it-infra-on-cloud/data-center')
      ON CONFLICT(site_code) DO UPDATE SET site_name=EXCLUDED.site_name,review_status='CONFIRMED',
        public_visible=true,commercial_scope_status='IN_SCOPE',commercial_model='MANAGED_SERVICE',
        commercial_review_status='CONFIRMED',commercial_scope_note=EXCLUDED.commercial_scope_note,
        commercial_source_url=EXCLUDED.commercial_source_url,facility_scope='COMMERCIAL',
        facility_review_status='CONFIRMED',facility_scope_note=EXCLUDED.facility_scope_note,
        facility_source_url=EXCLUDED.facility_source_url,updated_at=CURRENT_TIMESTAMP
    """)
    op.execute("""
      UPDATE dc_site SET facility_scope='CLOUD_SELF_USE',facility_review_status='CONFIRMED',
        facility_scope_note='사업자 공식 자료로 자체 클라우드·서비스 인프라 확인',
        facility_source_url=CASE WHEN site_code LIKE 'NAVER_GAK_%%'
          THEN 'https://datacenter.navercorp.com/' ELSE 'https://www.kakaocorp.com/page/detail/11097' END,
        updated_at=CURRENT_TIMESTAMP
      WHERE site_code IN ('NAVER_GAK_CHUNCHEON','NAVER_GAK_SEJONG','KAKAO_ANSAN')
    """)
    op.execute("""
      UPDATE dc_site SET site_name=replace(site_name,' 수집 검증 대상',''),
        facility_scope='ENTERPRISE',facility_review_status='NEEDS_EVIDENCE',
        facility_scope_note='기업 사업장 내 전용 IT센터 후보. 센터 실체·세부 주소·용량 추가 검증 필요',
        updated_at=CURRENT_TIMESTAMP
      WHERE site_code IN ('HYUNDAI_UIWANG_IT','SAMSUNG_SUWON_IT','SAMSUNG_GIHEUNG_IT',
        'SKHYNIX_ICHEON_IT','SKHYNIX_CHEONGJU_IT')
    """)
    op.execute("""
      UPDATE dc_site SET commercial_scope_status='IN_SCOPE',commercial_model='MANAGED_SERVICE',
        commercial_review_status='CONFIRMED',review_status='CONFIRMED',public_visible=true,
        facility_scope='COMMERCIAL',facility_review_status='CONFIRMED',
        commercial_scope_note=CASE WHEN site_code='LGCNS_JUKJEON'
          THEN 'LG CNS 공식 자료로 코로케이션·구축·운영 확인'
          ELSE 'LG CNS 공식 자료로 삼송 DBO 프로젝트 확인' END,
        commercial_source_url=CASE WHEN site_code='LGCNS_JUKJEON'
          THEN 'https://www.lgcns.com/kr/newsroom/press/detail.ko_0787'
          ELSE 'https://connect.lgcns.com/language-masters/ko/newsroom/press/detail.ax-2608-4' END,
        facility_scope_note='상용 데이터센터 범위에서 검토 완료',
        facility_source_url=CASE WHEN site_code='LGCNS_JUKJEON'
          THEN 'https://www.lgcns.com/kr/newsroom/press/detail.ko_0787'
          ELSE 'https://connect.lgcns.com/language-masters/ko/newsroom/press/detail.ax-2608-4' END,
        updated_at=CURRENT_TIMESTAMP
      WHERE site_code IN ('LGCNS_JUKJEON','LGCNS_SAMSONG_A','LGCNS_SAMSONG_B')
    """)
    op.execute("""
      INSERT INTO company_participation(company_id,scope_type,scope_id,role_code,review_status,
        confidence_score,evidence_url,public_visible,note)
      SELECT x.company_id,'SITE',s.site_id,x.role,x.status,x.confidence,x.url,true,
        '0029 기업·자체 데이터센터 관계'
      FROM dc_site s JOIN (VALUES
        ('LGCNS_INCHEON','ORG-002','OWNER','CONFIRMED',1.0,'https://www.lgcns.com/kr/service/modern-it-infra-on-cloud/data-center'),
        ('LGCNS_INCHEON','ORG-002','OPERATOR','CONFIRMED',1.0,'https://www.lgcns.com/kr/service/modern-it-infra-on-cloud/data-center'),
        ('LGCNS_JUKJEON','ORG-002','DBO_PROVIDER','CONFIRMED',1.0,'https://www.lgcns.com/kr/newsroom/press/detail.ko_0787'),
        ('LGCNS_JUKJEON','ORG-002','OPERATOR','CONFIRMED',1.0,'https://www.lgcns.com/kr/newsroom/press/detail.ko_0787'),
        ('LGCNS_SAMSONG_A','ORG-002','DBO_PROVIDER','CONFIRMED',1.0,'https://connect.lgcns.com/language-masters/ko/newsroom/press/detail.ax-2608-4'),
        ('LGCNS_SAMSONG_A','ORG-002','OPERATOR','CONFIRMED',0.9,'https://connect.lgcns.com/language-masters/ko/newsroom/press/detail.ax-2608-4'),
        ('LGCNS_SAMSONG_B','ORG-002','DBO_PROVIDER','CONFIRMED',1.0,'https://connect.lgcns.com/language-masters/ko/newsroom/press/detail.ax-2608-4'),
        ('LGCNS_SAMSONG_B','ORG-002','OPERATOR','CONFIRMED',0.9,'https://connect.lgcns.com/language-masters/ko/newsroom/press/detail.ax-2608-4'),
        ('NAVER_GAK_CHUNCHEON','ORG-005','OWNER','CONFIRMED',1.0,'https://datacenter.navercorp.com/gak/gak-chuncheon'),
        ('NAVER_GAK_CHUNCHEON','ORG-005','OPERATOR','CONFIRMED',1.0,'https://datacenter.navercorp.com/gak/gak-chuncheon'),
        ('NAVER_GAK_SEJONG','ORG-005','OWNER','CONFIRMED',1.0,'https://datacenter.navercorp.com/gaksejong/'),
        ('NAVER_GAK_SEJONG','ORG-005','OPERATOR','CONFIRMED',1.0,'https://datacenter.navercorp.com/gaksejong/'),
        ('KAKAO_ANSAN','ORG-011','OWNER','CONFIRMED',1.0,'https://www.kakaocorp.com/page/detail/11097'),
        ('KAKAO_ANSAN','ORG-011','OPERATOR','CONFIRMED',1.0,'https://www.kakaocorp.com/page/detail/11097'),
        ('HYUNDAI_UIWANG_IT','COMP_HYUNDAI_MOTOR','OWNER','CANDIDATE',0.6,NULL),
        ('HYUNDAI_UIWANG_IT','COMP_HYUNDAI_MOTOR','OPERATOR','CANDIDATE',0.6,NULL),
        ('SAMSUNG_SUWON_IT','COMP_SAMSUNG_ELEC','OWNER','CANDIDATE',0.6,NULL),
        ('SAMSUNG_SUWON_IT','COMP_SAMSUNG_ELEC','OPERATOR','CANDIDATE',0.6,NULL),
        ('SAMSUNG_GIHEUNG_IT','COMP_SAMSUNG_ELEC','OWNER','CANDIDATE',0.6,NULL),
        ('SAMSUNG_GIHEUNG_IT','COMP_SAMSUNG_ELEC','OPERATOR','CANDIDATE',0.6,NULL),
        ('SKHYNIX_ICHEON_IT','COMP_SK_HYNIX','OWNER','CANDIDATE',0.6,NULL),
        ('SKHYNIX_ICHEON_IT','COMP_SK_HYNIX','OPERATOR','CANDIDATE',0.6,NULL),
        ('SKHYNIX_CHEONGJU_IT','COMP_SK_HYNIX','OWNER','CANDIDATE',0.6,NULL),
        ('SKHYNIX_CHEONGJU_IT','COMP_SK_HYNIX','OPERATOR','CANDIDATE',0.6,NULL)
      ) x(site_code,company_id,role,status,confidence,url) ON s.site_code=x.site_code
      WHERE NOT EXISTS (SELECT 1 FROM company_participation cp WHERE cp.company_id=x.company_id
        AND cp.scope_type='SITE' AND cp.scope_id=s.site_id AND cp.role_code=x.role)
    """)
    op.execute("""
      INSERT INTO dc_project(project_code,site_id,project_name,project_type,project_scope,
        status_code,scope_note,rfs_date,review_status,public_visible)
      SELECT x.code,s.site_id,x.name,x.type,'WHOLE_SITE','OPERATING',x.note,x.rfs::date,'CONFIRMED',true
      FROM dc_site s JOIN (VALUES
        ('LGCNS_INCHEON','LGCNS_INCHEON_OP','LG CNS 인천 데이터센터 운영','ENTERPRISE','LG CNS 공식 운영센터',NULL),
        ('NAVER_GAK_CHUNCHEON','NAVER_GAK_CHUNCHEON_OP','네이버 각 춘천 운영','ENTERPRISE','네이버 자체 데이터센터','2013-06-01'),
        ('NAVER_GAK_SEJONG','NAVER_GAK_SEJONG_OP','네이버 각 세종 운영','HYPERSCALE','네이버 자체 하이퍼스케일 데이터센터','2023-11-01'),
        ('KAKAO_ANSAN','KAKAO_ANSAN_OP','카카오 데이터센터 안산 운영','HYPERSCALE','카카오 자체 데이터센터','2024-01-01'),
        ('LGCNS_JUKJEON','LGCNS_JUKJEON_OP','LG CNS 죽전 데이터센터 운영','COLOCATION','상용 코로케이션 운영','2025-09-01')
      ) x(site_code,code,name,type,note,rfs) ON s.site_code=x.site_code
      ON CONFLICT(project_code) DO UPDATE SET status_code='OPERATING',
        rfs_date=COALESCE(EXCLUDED.rfs_date,dc_project.rfs_date),review_status='CONFIRMED',
        public_visible=true,updated_at=CURRENT_TIMESTAMP
    """)
    op.execute("""
      INSERT INTO capacity_snapshot(scope_type,scope_id,capacity_type_code,raw_value,raw_unit,
        raw_phrase,normalized_value_mw,normalized_value,normalized_unit,capacity_stage,
        measurement_basis,document_url,review_status,aggregation_excluded,exclusion_reason,note)
      SELECT 'PROJECT',p.project_id,'GRID_INTAKE_MW',x.mw::text,'MW',x.phrase,x.mw,x.mw,
        'MW','OPERATING','PUBLISHED_CAPACITY',x.url,'CONFIRMED',x.excluded,
        CASE WHEN x.excluded THEN x.note ELSE NULL END,x.note
      FROM dc_project p JOIN (VALUES
        ('NAVER_GAK_CHUNCHEON_OP',40::numeric,'최대 40,000kW',true,'자체센터이므로 상용 공급량 제외','https://datacenter.navercorp.com/gak/gak-chuncheon'),
        ('NAVER_GAK_SEJONG_OP',270::numeric,'최대 270MW',true,'자체센터이므로 상용 공급량 제외','https://datacenter.navercorp.com/gak'),
        ('LGCNS_JUKJEON_OP',100::numeric,'수전용량 100MW',false,'상용 코로케이션 수전용량','https://www.lgcns.com/kr/newsroom/press/detail.ko_0787')
      ) x(code,mw,phrase,excluded,note,url) ON p.project_code=x.code
      WHERE NOT EXISTS (SELECT 1 FROM capacity_snapshot cs WHERE cs.scope_type='PROJECT'
        AND cs.scope_id=p.project_id AND cs.capacity_type_code='GRID_INTAKE_MW')
    """)
    op.execute("""
      INSERT INTO evidence_document(source_id,canonical_url,external_document_id,title,
        document_type,publisher,language_code,source_grade,access_scope,review_status,
        reviewed_by,reviewed_at,review_note)
      SELECT sr.source_id,x.url,x.external_id,x.title,'WEB_PAGE',x.publisher,'ko','A','PUBLIC',
        'CONFIRMED','migration-0029',CURRENT_TIMESTAMP,'기업 전용·자체 클라우드·LG CNS 센터 공식 근거 확인'
      FROM source_registry sr JOIN (VALUES
        ('LG_CNS_OFFICIAL','https://www.lgcns.com/kr/service/modern-it-infra-on-cloud/data-center','official:lgcns-dc-portfolio','LG CNS 데이터센터 포트폴리오','LG CNS'),
        ('LG_CNS_OFFICIAL','https://www.lgcns.com/kr/newsroom/press/detail.ko_0787','official:lgcns-jukjeon','LG CNS 죽전 데이터센터 구축·운영','LG CNS'),
        ('LG_CNS_OFFICIAL','https://connect.lgcns.com/language-masters/ko/newsroom/press/detail.ax-2608-4','official:lgcns-samsong','LG CNS 삼송 AI 데이터센터','LG CNS'),
        ('GOOGLE_NEWS_DC','https://datacenter.navercorp.com/','official:naver-gak','네이버 데이터센터 각','네이버'),
        ('GOOGLE_NEWS_DC','https://www.kakaocorp.com/page/detail/11097','official:kakao-ansan','카카오 데이터센터 안산','카카오')
      ) x(source_code,url,external_id,title,publisher) ON sr.source_code=x.source_code
      WHERE NOT EXISTS (
        SELECT 1 FROM evidence_document ed
        WHERE ed.source_id=sr.source_id AND ed.external_document_id=x.external_id
      )
    """)


def downgrade() -> None:
    op.execute("DELETE FROM source_feed WHERE feed_code='GNEWS_ENTERPRISE_DC'")
    op.execute("DELETE FROM capacity_snapshot WHERE note IN ('자체센터이므로 상용 공급량 제외','상용 코로케이션 수전용량')")
    op.execute("DELETE FROM dc_project WHERE project_code IN ('LGCNS_INCHEON_OP','NAVER_GAK_CHUNCHEON_OP','NAVER_GAK_SEJONG_OP','KAKAO_ANSAN_OP','LGCNS_JUKJEON_OP')")
    op.execute("DELETE FROM company_participation WHERE note='0029 기업·자체 데이터센터 관계'")
    op.execute("DELETE FROM evidence_document WHERE reviewed_by='migration-0029'")
    op.execute("DELETE FROM dc_site WHERE site_code='LGCNS_INCHEON'")
    op.execute("DELETE FROM company WHERE company_id IN ('COMP_HYUNDAI_MOTOR','COMP_SAMSUNG_ELEC','COMP_SK_HYNIX') AND NOT EXISTS (SELECT 1 FROM company_participation cp WHERE cp.company_id=company.company_id)")
    op.drop_index("idx_dc_site_facility_scope", table_name="dc_site")
    op.drop_constraint("ck_dc_site_facility_review", "dc_site", type_="check")
    op.drop_constraint("ck_dc_site_facility_scope", "dc_site", type_="check")
    op.drop_column("dc_site", "facility_source_url")
    op.drop_column("dc_site", "facility_scope_note")
    op.drop_column("dc_site", "facility_review_status")
    op.drop_column("dc_site", "facility_scope")
