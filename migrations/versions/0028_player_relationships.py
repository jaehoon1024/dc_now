"""Connect the full player roster and add newly verified developers.

Revision ID: 0028_player_relationships
Revises: 0027_player_intelligence
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0028_player_relationships"
down_revision: Union[str, None] = "0027_player_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO company_role_type(role_code,role_name,description)
        VALUES('PF_ARRANGER','PF 주선사','프로젝트파이낸싱 구조 설계·주선·금융조달 수행사')
        ON CONFLICT(role_code) DO UPDATE SET
            role_name=EXCLUDED.role_name,description=EXCLUDED.description,active=true
    """)
    op.execute("""
        INSERT INTO company(company_id,standard_name,legal_name,official_url,review_status,note)
        VALUES
          ('COMP_YIDO','이도','주식회사 이도','https://www.yido.com/','CONFIRMED','청라 50MW 데이터센터 개발·운영'),
          ('COMP_EUGENE_SEC','유진투자증권','유진투자증권 주식회사','https://www.eugenefn.com/','CONFIRMED','데이터센터 PF 금융 주선'),
          ('COMP_KAAM','한국대체투자자산운용(KAAM)','한국대체투자자산운용 주식회사','https://www.kaam.kr/','CONFIRMED','안산 데이터센터 개발 펀드 운용'),
          ('COMP_ONEASIA','OneAsia Network','OneAsia Network Limited','https://www.oneas1a.com/','CONFIRMED','부산 미음 상용 데이터센터 개발·운영'),
          ('COMP_KEPPEL','Keppel','Keppel Ltd.', 'https://www.keppel.com/','CONFIRMED','안산 60MW 데이터센터 투자·개발'),
          ('COMP_EPOCH','Epoch Digital','Epoch Digital',NULL,'CONFIRMED','안양 상용 데이터센터 운영')
        ON CONFLICT(company_id) DO UPDATE SET
          official_url=COALESCE(EXCLUDED.official_url,company.official_url),
          review_status='CONFIRMED',note=EXCLUDED.note,updated_at=CURRENT_TIMESTAMP
    """)
    op.execute("""
        INSERT INTO source_registry(
          source_code,source_name,source_type,base_url,default_source_grade,
          collection_method,collection_interval,terms_review_status,owner_name,
          active,note,collection_policy,content_storage_policy,
          robots_review_status,request_interval_seconds,allowed_content_scope,
          compliance_checked_on,legal_approval_required,compliance_note
        )
        SELECT x.code,x.name,'COMPANY',x.url,'B','MANUAL','MONTHLY','LIMITED',
               x.owner,true,'공식 공개 자료의 센터·프로젝트·회사 관계',
               'MANUAL_ONLY','URL_ONLY','NOT_REVIEWED',30,
               '공식 페이지에서 확인한 공개 사실과 URL만 저장',CURRENT_DATE,true,
               '자동수집 전 robots·이용조건 별도 검토'
        FROM (VALUES
          ('YIDO_OFFICIAL','이도 공식 자료','https://www.yido.com/','이도'),
          ('KAAM_OFFICIAL','한국대체투자자산운용 공식 자료','https://www.kaam.kr/','한국대체투자자산운용'),
          ('ONEASIA_OFFICIAL','OneAsia 공식 자료','https://www.oneas1a.com/','OneAsia Network'),
          ('KEPPEL_OFFICIAL','Keppel 공식 자료','https://www.keppel.com/','Keppel')
        ) x(code,name,url,owner)
        ON CONFLICT(source_code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO source_feed(
          source_id,feed_code,feed_name,feed_url,feed_format,filter_mode,
          filter_keywords,storage_policy,request_interval_seconds,active,note
        )
        SELECT source_id,'GNEWS_PLAYER_EXPANSION','신규 개발·금융 플레이어',
          'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%EC%9D%B4%EB%8F%84+OR+YIDO+OR+%EC%9C%A0%EC%A7%84%ED%88%AC%EC%9E%90%EC%A6%9D%EA%B6%8C+OR+KAAM+OR+%ED%95%9C%EA%B5%AD%EB%8C%80%EC%B2%B4%ED%88%AC%EC%9E%90%EC%9E%90%EC%82%B0%EC%9A%B4%EC%9A%A9+OR+%EC%9B%90%EC%95%84%EC%8B%9C%EC%95%84+OR+OneAsia+OR+%EC%BC%80%ED%8E%A0+OR+Keppel%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako',
          'RSS','ALL','[]'::jsonb,'METADATA_ONLY',15,true,
          '신규 데이터센터 개발·자산운용·PF 플레이어 제목·URL·게시일 탐색'
        FROM source_registry WHERE source_code='GOOGLE_NEWS_DC'
        ON CONFLICT(feed_url) DO UPDATE SET active=true,updated_at=CURRENT_TIMESTAMP
    """)

    op.execute("""
        INSERT INTO dc_site(
          site_code,site_name,site_name_raw,address_raw,address_standard,sido,sigungu,
          review_status,public_visible,commercial_scope_status,commercial_model,
          commercial_review_status,commercial_scope_note,commercial_source_url
        ) VALUES
          ('YIDO_CHEONGNA','이도 청라 데이터센터','이도 청라 데이터센터','인천 청라국제도시','인천광역시 서구 청라국제도시','인천광역시','서구','CONFIRMED',true,'IN_SCOPE','WHOLESALE','CONFIRMED','이도 공식 계열사 페이지에서 청라 50MW 개발·운영 확인','https://yidoterraone.com/aiinfra?section=section3'),
          ('KAAM_ANSAN','KAAM 캄스퀘어 안산 데이터센터','캄스퀘어 안산 데이터센터','경기도 안산시','경기도 안산시','경기도','안산시','CONFIRMED',true,'IN_SCOPE','WHOLESALE','CONFIRMED','KAAM 공식 운용펀드에서 안산 데이터센터 개발사업 투자 확인','https://www.kaam.kr/page/dv03'),
          ('ONEASIA_BUSAN','OneAsia 부산 데이터센터','OneAsia Busan Data Centre','부산광역시 강서구 미음산업단지','부산광역시 강서구 미음산업단지','부산광역시','강서구','CONFIRMED',true,'IN_SCOPE','COLOCATION','CONFIRMED','OneAsia 공식 한국 센터·코로케이션 서비스와 미음산업단지 개발 확인','https://www.oneas1a.com/korea/'),
          ('IGIS_HANAM','이지스 하남 데이터센터','이지스 하남 데이터센터','경기도 하남시','경기도 하남시','경기도','하남시','CONFIRMED',true,'IN_SCOPE','COLOCATION','CONFIRMED','이지스 개발 및 삼성물산 시공, LG CNS 운영 관계의 상용 센터','https://www.igisam.com/en/insight-news/insight/detail/15576'),
          ('MASTERN_GWACHEON','마스턴 과천 데이터센터','마스턴 과천 데이터센터','경기도 과천시 주암지구','경기도 과천시 주암지구','경기도','과천시','CONFIRMED',true,'IN_SCOPE','WHOLESALE','CONFIRMED','마스턴 프로젝트리츠 개발 추진 공개자료 확인','https://www.dnews.co.kr/uhtml/view.jsp?idxno=202607071313053010244'),
          ('EPOCH_ANYANG','에포크 안양 데이터센터','에포크 안양 센터','경기도 안양시 동안구 호계동','경기도 안양시 동안구 호계동','경기도','안양시','CONFIRMED',true,'IN_SCOPE','COLOCATION','CONFIRMED','GS건설 개발·시공 및 운영 밸류체인 공개자료 확인','https://www.cerik.re.kr/uploads/report/3018/%EA%B1%B4%EC%84%A4%EB%8F%99%ED%96%A5%EB%B8%8C%EB%A6%AC%ED%95%91%201029%ED%98%B8.pdf')
        ON CONFLICT(site_code) DO NOTHING
    """)
    # EPOCH_ANYANG may already exist as a discovery candidate. Promote the
    # existing row after the official/industry evidence has been reviewed.
    op.execute("""
        UPDATE dc_site SET
          commercial_scope_status='IN_SCOPE',commercial_model='COLOCATION',
          commercial_review_status='CONFIRMED',review_status='CONFIRMED',public_visible=true,
          commercial_scope_note='GS건설 개발·시공 및 운영 밸류체인 공개자료 확인',
          commercial_source_url='https://www.cerik.re.kr/uploads/report/3018/%EA%B1%B4%EC%84%A4%EB%8F%99%ED%96%A5%EB%B8%8C%EB%A6%AC%ED%95%91%201029%ED%98%B8.pdf',
          updated_at=CURRENT_TIMESTAMP
        WHERE site_code='EPOCH_ANYANG'
    """)
    op.execute("""
        UPDATE dc_site SET
          commercial_scope_status='IN_SCOPE',commercial_model='WHOLESALE',
          commercial_review_status='CONFIRMED',review_status='CONFIRMED',public_visible=true,
          commercial_scope_note='Keppel 공식 60MW 안산 AI 데이터센터 개발 발표 확인',
          commercial_source_url='https://www.keppel.com/media/keppel-enters-south-koreas-fast-growing-data-centre-market/',
          updated_at=CURRENT_TIMESTAMP
        WHERE site_code='KEPPEL_ANSAN'
    """)
    op.execute("""
        UPDATE dc_site SET
          commercial_scope_status='IN_SCOPE',commercial_model='COLOCATION',
          commercial_review_status='CONFIRMED',review_status='CONFIRMED',public_visible=true,
          commercial_scope_note='DL이앤씨 공식 준공자료에서 DCI 합작 상용 가산 데이터센터 확인',
          commercial_source_url='https://m.dlenc.co.kr/pr/InfoView.do?no_ntc_plte_sral=26401',
          updated_at=CURRENT_TIMESTAMP
        WHERE site_code='DCI_SEOUL01'
    """)
    op.execute("""
        UPDATE dc_site SET
          commercial_scope_status='IN_SCOPE',commercial_model='COLOCATION',
          commercial_review_status='CONFIRMED',review_status='CONFIRMED',public_visible=true,
          commercial_scope_note='kt cloud 공식 코로케이션 서비스 및 센터 목록 확인',
          commercial_source_url='https://www.ktcloud.com/service/idc',updated_at=CURRENT_TIMESTAMP
        WHERE site_code IN ('KT_GASAN','KT_GANGNAM','KT_NAMGURO','KT_MOKDONG1',
          'KT_MOKDONG2','KT_YEOUIDO','KT_YONGSAN')
    """)

    op.execute("""
        INSERT INTO dc_project(
          project_code,site_id,project_name,project_type,project_scope,status_code,
          scope_note,planned_rfs_date,planned_rfs_precision,planned_rfs_period,
          rfs_date,review_status,public_visible
        )
        SELECT x.project_code,s.site_id,x.project_name,x.project_type,'WHOLE_SITE',
               x.status_code,x.note,x.planned::date,x.precision,x.period,
               x.actual::date,'CONFIRMED',true
        FROM dc_site s JOIN (VALUES
          ('YIDO_CHEONGNA','YIDO_CHEONGNA_DEV','이도 청라 데이터센터 개발','HYPERSCALE','SITE_SECURED','수도권 50MW 개발·운영 추진',NULL,NULL,NULL,NULL),
          ('KAAM_ANSAN','KAAM_ANSAN_DEV','KAAM 캄스퀘어 안산 데이터센터 개발','HYPERSCALE','POWER_SECURED','공식 펀드 투자 대상 안산 개발사업',NULL,NULL,NULL,NULL),
          ('ONEASIA_BUSAN','ONEASIA_BUSAN_DEV','OneAsia 부산 데이터센터 개발','HYPERSCALE','READY','공식 서비스 예정월 기준','2026-08-01','MONTH','2026-08',NULL),
          ('KEPPEL_ANSAN','KEPPEL_ANSAN_DEV','Keppel 안산 데이터센터 개발','HYPERSCALE','SITE_SECURED','인허가·전력 확보, 2030 RFS 목표','2030-01-01','YEAR','2030',NULL),
          ('IGIS_HANAM','IGIS_HANAM_OP','이지스 하남 데이터센터 운영','COLOCATION','OPERATING','2024년 준공·운영','2024-03-01','MONTH','2024-03','2024-03-01'),
          ('MASTERN_GWACHEON','MASTERN_GWACHEON_DEV','마스턴 과천 데이터센터 개발','HYPERSCALE','SITE_SECURED','프로젝트리츠 개발 추진',NULL,NULL,NULL,NULL),
          ('EPOCH_ANYANG','EPOCH_ANYANG_OP','에포크 안양 데이터센터 운영','COLOCATION','OPERATING','2024년 1월 준공','2024-01-01','MONTH','2024-01','2024-01-01'),
          ('DCI_SEOUL01','DCI_SEOUL01_OP','DCI 가산 데이터센터 운영','COLOCATION','OPERATING','2025년 9월 준공','2025-09-01','MONTH','2025-09','2025-09-01')
        ) x(site_code,project_code,project_name,project_type,status_code,note,planned,precision,period,actual)
          ON s.site_code=x.site_code
        ON CONFLICT(project_code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO capacity_snapshot(
          scope_type,scope_id,capacity_type_code,raw_value,raw_unit,raw_phrase,
          normalized_value_mw,normalized_value,normalized_unit,capacity_stage,
          measurement_basis,document_url,review_status,aggregation_excluded,
          exclusion_reason,note
        )
        SELECT 'PROJECT',p.project_id,'GRID_INTAKE_MW',x.mw::text,'MW',x.phrase,
               x.mw,x.mw,'MW',x.stage,'PUBLISHED_CAPACITY',x.url,'CONFIRMED',false,NULL,
               '공개자료에서 수전용량으로 확인'
        FROM dc_project p JOIN (VALUES
          ('YIDO_CHEONGNA_DEV',50::numeric,'수전용량 50MW','SECURED','https://yidoterraone.com/aiinfra?section=section3'),
          ('KEPPEL_ANSAN_DEV',60::numeric,'60MW greenfield data centre','SECURED','https://www.keppel.com/media/keppel-enters-south-koreas-fast-growing-data-centre-market/'),
          ('DCI_SEOUL01_OP',20::numeric,'수전용량 20MW','OPERATING','https://m.dlenc.co.kr/pr/InfoView.do?no_ntc_plte_sral=26401'),
          ('EPOCH_ANYANG_OP',40::numeric,'40MW 데이터센터','OPERATING','https://www.cerik.re.kr/uploads/report/3018/%EA%B1%B4%EC%84%A4%EB%8F%99%ED%96%A5%EB%B8%8C%EB%A6%AC%ED%95%91%201029%ED%98%B8.pdf')
        ) x(project_code,mw,phrase,stage,url) ON p.project_code=x.project_code
    """)
    op.execute("""
        INSERT INTO capacity_snapshot(
          scope_type,scope_id,capacity_type_code,raw_value,raw_unit,raw_phrase,
          normalized_value_mw,normalized_value,normalized_unit,capacity_stage,
          measurement_basis,document_url,review_status,aggregation_excluded,note
        )
        SELECT 'PROJECT',p.project_id,'IT_LOAD_MW','12.9','MW','IT Load 12.9MW',
               12.9,12.9,'MW','OPERATING','PUBLISHED_CAPACITY',
               'https://m.dlenc.co.kr/pr/InfoView.do?no_ntc_plte_sral=26401',
               'CONFIRMED',false,'DL이앤씨 공식 준공자료 기준'
        FROM dc_project p WHERE p.project_code='DCI_SEOUL01_OP'
    """)

    op.execute("""
        INSERT INTO company_participation(
          company_id,scope_type,scope_id,role_code,review_status,confidence_score,
          evidence_url,public_visible,note
        )
        SELECT x.company_id,'SITE',s.site_id,x.role,'CONFIRMED',x.confidence,
               x.url,true,'0028 플레이어 관계 보강'
        FROM dc_site s JOIN (VALUES
          ('YIDO_CHEONGNA','COMP_YIDO','DEVELOPER',1.0,'https://yidoterraone.com/aiinfra?section=section3'),
          ('YIDO_CHEONGNA','COMP_YIDO','OPERATOR',1.0,'https://yidoterraone.com/aiinfra?section=section3'),
          ('YIDO_CHEONGNA','COMP_YIDO','ASSET_MANAGER',1.0,'https://www.yido.com/'),
          ('KAAM_ANSAN','COMP_KAAM','ASSET_MANAGER',1.0,'https://www.kaam.kr/page/dv03'),
          ('KAAM_ANSAN','COMP_KAAM','DEVELOPER',0.9,'https://www.kaam.kr/page/dv03'),
          ('KAAM_ANSAN','COMP_EUGENE_SEC','PF_ARRANGER',0.8,'https://m.thebell.co.kr/m/newsview.asp?newskey=202509152218105520102464'),
          ('ONEASIA_BUSAN','COMP_ONEASIA','OWNER',1.0,'https://www.oneas1a.com/newsandevent/page/3/'),
          ('ONEASIA_BUSAN','COMP_ONEASIA','DEVELOPER',1.0,'https://www.oneas1a.com/newsandevent/'),
          ('ONEASIA_BUSAN','COMP_ONEASIA','OPERATOR',1.0,'https://www.oneas1a.com/korea/'),
          ('KEPPEL_ANSAN','COMP_KEPPEL','OWNER',1.0,'https://www.keppel.com/media/keppel-enters-south-koreas-fast-growing-data-centre-market/'),
          ('KEPPEL_ANSAN','COMP_KEPPEL','DEVELOPER',1.0,'https://www.keppel.com/media/keppel-enters-south-koreas-fast-growing-data-centre-market/'),
          ('KEPPEL_ANSAN','COMP_KEPPEL','OPERATOR',0.9,'https://www.keppel.com/media/keppel-enters-south-koreas-fast-growing-data-centre-market/'),
          ('KEPPEL_ANSAN','ORG-017','BUILDER',0.8,'https://www.dealbook.co.kr/kepel-ansan-deiteosenteo-gaebalsaeob-8000eog-bonpf-jodal-sidong/'),
          ('PDG_SE1','ORG-014','ASSET_MANAGER',0.9,'https://www.esr.com/news/esr-and-wide-creek-amc-to-develop-first-data-centre-in-south-korea/'),
          ('IGIS_HANAM','ORG-012','ASSET_MANAGER',1.0,'https://www.igisam.com/en/insight-news/insight/detail/15576'),
          ('IGIS_HANAM','ORG-016','BUILDER',0.9,'https://www.hmsec.com/documents/research/20240418172036383_ko.pdf'),
          ('IGIS_HANAM','ORG-002','OPERATOR',1.0,'https://www.igisam.com/ko/insight-news/insight/portfolio-insights'),
          ('MASTERN_GWACHEON','ORG-015','ASSET_MANAGER',0.9,'https://www.dnews.co.kr/uhtml/view.jsp?idxno=202607071313053010244'),
          ('EPOCH_ANYANG','ORG-018','DEVELOPER',0.9,'https://www.cerik.re.kr/uploads/report/3018/%EA%B1%B4%EC%84%A4%EB%8F%99%ED%96%A5%EB%B8%8C%EB%A6%AC%ED%95%91%201029%ED%98%B8.pdf'),
          ('EPOCH_ANYANG','ORG-018','BUILDER',0.9,'https://v.daum.net/v/20260824043245406'),
          ('EPOCH_ANYANG','COMP_EPOCH','OPERATOR',0.9,'https://www.cerik.re.kr/uploads/report/3018/%EA%B1%B4%EC%84%A4%EB%8F%99%ED%96%A5%EB%B8%8C%EB%A6%AC%ED%95%91%201029%ED%98%B8.pdf'),
          ('DCI_SEOUL01','COMP_DCI','DEVELOPER',1.0,'https://m.dlenc.co.kr/pr/InfoView.do?no_ntc_plte_sral=26401'),
          ('DCI_SEOUL01','COMP_DCI','OPERATOR',1.0,'https://m.dlenc.co.kr/pr/InfoView.do?no_ntc_plte_sral=26401'),
          ('DCI_SEOUL01','ORG-019','BUILDER',1.0,'https://m.dlenc.co.kr/pr/InfoView.do?no_ntc_plte_sral=26401'),
          ('DIGITALEDGE_SEL3','ORG-020','BUILDER',0.9,'https://www.skecoplant.com/contents/boardView?contentsNo=IYV3ueJ6ZM&contentsOrders=1&languageCode=CM030001&menuCode=M6100')
        ) x(site_code,company_id,role,confidence,url) ON s.site_code=x.site_code
        WHERE NOT EXISTS(
          SELECT 1 FROM company_participation cp
          WHERE cp.company_id=x.company_id AND cp.scope_type='SITE'
            AND cp.scope_id=s.site_id AND cp.role_code=x.role
        )
    """)
    op.execute("""
        INSERT INTO company_participation(
          company_id,scope_type,scope_id,role_code,review_status,confidence_score,
          evidence_url,public_visible,note
        )
        SELECT 'ORG-004','SITE',site_id,'OPERATOR','CONFIRMED',0.95,
               'https://www.ktcloud.com/service/idc',true,'0028 플레이어 관계 보강'
        FROM dc_site s
        WHERE (site_code LIKE 'KT_%%' OR site_name ILIKE 'KT Cloud%%')
          AND record_status='ACTIVE'
          AND NOT EXISTS(
            SELECT 1 FROM company_participation cp WHERE cp.company_id='ORG-004'
              AND cp.scope_type='SITE' AND cp.scope_id=s.site_id AND cp.role_code='OPERATOR'
          )
    """)

    op.execute("""
        INSERT INTO evidence_document(
          source_id,canonical_url,external_document_id,title,document_type,publisher,
          published_at,language_code,source_grade,access_scope,review_status,
          reviewed_by,reviewed_at,review_note
        )
        SELECT sr.source_id,x.url,x.external_id,x.title,'WEB_PAGE',x.publisher,
               x.published::timestamptz,x.lang,'B','PUBLIC','CONFIRMED',
               'migration-0028',CURRENT_TIMESTAMP,'공식 자료로 플레이어·센터·개발 관계 확인'
        FROM source_registry sr JOIN (VALUES
          ('YIDO_OFFICIAL','https://yidoterraone.com/aiinfra?section=section3','official:yido-cheongna-dc','이도 청라 50MW 데이터센터 개발사업','이도',NULL,'ko'),
          ('KAAM_OFFICIAL','https://www.kaam.kr/page/dv03','official:kaam-ansan-fund','KAAM 안산 데이터센터 개발 펀드','한국대체투자자산운용',NULL,'ko'),
          ('ONEASIA_OFFICIAL','https://www.oneas1a.com/korea/','official:oneasia-busan-korea','OneAsia Korea Busan Data Centre','OneAsia Network',NULL,'en'),
          ('ONEASIA_OFFICIAL','https://www.oneas1a.com/newsandevent/','official:oneasia-busan-groundbreaking','OneAsia Breaks Ground on Busan Data Centre','OneAsia Network','2024-02-01','en'),
          ('KEPPEL_OFFICIAL','https://www.keppel.com/media/keppel-enters-south-koreas-fast-growing-data-centre-market/','official:keppel-ansan-60mw','Keppel enters South Korea data centre market with 60MW Ansan project','Keppel',NULL,'en')
        ) x(source_code,url,external_id,title,publisher,published,lang)
          ON sr.source_code=x.source_code
        WHERE NOT EXISTS(
          SELECT 1 FROM evidence_document ed
          WHERE ed.source_id=sr.source_id AND ed.external_document_id=x.external_id
        )
    """)


def downgrade() -> None:
    op.execute("DELETE FROM evidence_document WHERE external_document_id LIKE 'official:yido-%%' OR external_document_id LIKE 'official:kaam-%%' OR external_document_id LIKE 'official:oneasia-%%' OR external_document_id LIKE 'official:keppel-%%'")
    op.execute("DELETE FROM company_participation WHERE note='0028 플레이어 관계 보강'")
    op.execute("DELETE FROM capacity_snapshot WHERE scope_type='PROJECT' AND scope_id IN (SELECT project_id FROM dc_project WHERE project_code IN ('YIDO_CHEONGNA_DEV','KAAM_ANSAN_DEV','ONEASIA_BUSAN_DEV','KEPPEL_ANSAN_DEV','IGIS_HANAM_OP','MASTERN_GWACHEON_DEV','EPOCH_ANYANG_OP','DCI_SEOUL01_OP'))")
    op.execute("DELETE FROM dc_project WHERE project_code IN ('YIDO_CHEONGNA_DEV','KAAM_ANSAN_DEV','ONEASIA_BUSAN_DEV','KEPPEL_ANSAN_DEV','IGIS_HANAM_OP','MASTERN_GWACHEON_DEV','EPOCH_ANYANG_OP','DCI_SEOUL01_OP')")
    op.execute("DELETE FROM dc_site WHERE site_code IN ('YIDO_CHEONGNA','KAAM_ANSAN','ONEASIA_BUSAN','IGIS_HANAM','MASTERN_GWACHEON','EPOCH_ANYANG')")
    op.execute("DELETE FROM company WHERE company_id IN ('COMP_YIDO','COMP_EUGENE_SEC','COMP_KAAM','COMP_ONEASIA','COMP_KEPPEL','COMP_EPOCH') AND NOT EXISTS (SELECT 1 FROM company_participation cp WHERE cp.company_id=company.company_id)")
    op.execute("DELETE FROM source_feed WHERE feed_code='GNEWS_PLAYER_EXPANSION'")
    op.execute("DELETE FROM source_registry WHERE source_code IN ('YIDO_OFFICIAL','KAAM_OFFICIAL','ONEASIA_OFFICIAL','KEPPEL_OFFICIAL')")
    op.execute("DELETE FROM company_role_type WHERE role_code='PF_ARRANGER'")
