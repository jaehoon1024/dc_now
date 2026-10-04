"""Add player-focused collection and verified commercial relationships.

Revision ID: 0027_player_intelligence
Revises: 0026_commercial_development
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0027_player_intelligence"
down_revision: Union[str, None] = "0026_commercial_development"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO source_registry (
            source_code, source_name, source_type, base_url,
            default_source_grade, collection_method, collection_interval,
            terms_review_status, owner_name, active, note,
            collection_policy, content_storage_policy, robots_review_status,
            request_interval_seconds, allowed_content_scope,
            compliance_checked_on, legal_approval_required, compliance_note
        ) VALUES (
            'KORAMCO_OFFICIAL','코람코자산신탁·자산운용 공식 자료','COMPANY',
            'https://www.koramco.com/','B','MANUAL','MONTHLY','LIMITED',
            '코람코자산신탁·코람코자산운용',true,
            '공식 포트폴리오·회사소식의 데이터센터 개발 및 운영 현황',
            'MANUAL_ONLY','URL_ONLY','NOT_REVIEWED',30,
            '공개 화면에서 확인한 센터명·상태·역할·발표용량과 원문 URL만 저장',
            CURRENT_DATE,true,'자동수집 전 robots·이용조건 별도 검토'
        ) ON CONFLICT (source_code) DO NOTHING
    """)

    op.execute("""
        INSERT INTO source_feed (
            source_id, feed_code, feed_name, feed_url, feed_format,
            filter_mode, filter_keywords, storage_policy,
            request_interval_seconds, active, note
        )
        SELECT source_id, feed_code, feed_name, feed_url, 'RSS', 'ALL',
               '[]'::jsonb, 'METADATA_ONLY', 15, true,
               '국내 상용 데이터센터 플레이어별 제목·URL·게시일·발행기관 탐색'
        FROM source_registry
        CROSS JOIN (VALUES
            ('GNEWS_PLAYER_IT_SERVICE','IT서비스·통신 운영사',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%22LG+CNS%22+OR+%22%EC%82%BC%EC%84%B1SDS%22+OR+%22%EB%A1%AF%EB%8D%B0%EC%9D%B4%EB%85%B8%EB%B2%A0%EC%9D%B4%ED%8A%B8%22+OR+%22KT+cloud%22+OR+%22SK%EB%B8%8C%EB%A1%9C%EB%93%9C%EB%B0%B4%EB%93%9C%22+OR+%22LG%EC%9C%A0%ED%94%8C%EB%9F%AC%EC%8A%A4%22%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_PLAYER_ASSET_MANAGER','자산운용사·AMC',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%EC%BD%94%EB%9E%8C%EC%BD%94+OR+%EC%9D%B4%EC%A7%80%EC%8A%A4%EC%9E%90%EC%82%B0%EC%9A%B4%EC%9A%A9+OR+%EB%A7%88%EC%8A%A4%ED%84%B4%ED%88%AC%EC%9E%90%EC%9A%B4%EC%9A%A9+OR+ESR%EC%BC%84%EB%8B%AC%EC%8A%A4%ED%80%98%EC%96%B4+OR+%ED%95%9C%EA%B5%AD%ED%88%AC%EC%9E%90%EB%A6%AC%EC%96%BC%EC%97%90%EC%85%8B%EC%9A%B4%EC%9A%A9+OR+%EC%99%80%EC%9D%B4%EB%93%9C%ED%81%AC%EB%A6%AD%EC%9E%90%EC%82%B0%EC%9A%B4%EC%9A%A9%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_PLAYER_GLOBAL_OPERATOR','글로벌 상용 운영사',
             'https://news.google.com/rss/search?q=%28%22South+Korea%22+OR+%ED%95%9C%EA%B5%AD%29+%28%22data+center%22+OR+%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%29+%28%22Digital+Edge%22+OR+%22Digital+Realty%22+OR+Equinix+OR+Empyrion+OR+%22Princeton+Digital%22+OR+PDG+OR+DCI%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_PLAYER_BUILDER','시공사·DBO',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%EC%82%BC%EC%84%B1%EB%AC%BC%EC%82%B0+OR+%ED%98%84%EB%8C%80%EA%B1%B4%EC%84%A4+OR+GS%EA%B1%B4%EC%84%A4+OR+DL%EC%9D%B4%EC%95%A4%EC%94%A8+OR+SK%EC%97%90%EC%BD%94%ED%94%8C%EB%9E%9C%ED%8A%B8%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_PLAYER_CAPITAL','인프라 투자자·PE',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28Actis+OR+Stonepeak+OR+Brookfield+OR+Invesco+OR+Macquarie+OR+CapitaLand+OR+Seraya%29+when%3A365d&hl=ko&gl=KR&ceid=KR%3Ako')
        ) AS feeds(feed_code, feed_name, feed_url)
        WHERE source_code='GOOGLE_NEWS_DC'
        ON CONFLICT (feed_url) DO UPDATE SET
            active=true, note=EXCLUDED.note, updated_at=CURRENT_TIMESTAMP
    """)

    # Samsung SDS publishes the five Korean data-center addresses and confirms
    # that the facilities support paid enterprise cloud and managed services.
    op.execute("""
        UPDATE dc_site SET
            address_standard=CASE site_code
                WHEN 'SAMSUNG_SDS_CHUNCHEON' THEN '강원특별자치도 춘천시 옛경춘로 409-14'
                WHEN 'SAMSUNG_SDS_DONGTAN' THEN '경기도 화성시 동탄대로9나길 14'
                WHEN 'SAMSUNG_SDS_GUMI' THEN '경상북도 구미시 3공단3로 302'
                ELSE address_standard END,
            location_precision=CASE WHEN site_code IN (
                'SAMSUNG_SDS_CHUNCHEON','SAMSUNG_SDS_DONGTAN','SAMSUNG_SDS_GUMI'
            ) THEN 'ROAD' ELSE location_precision END,
            coordinate_quality=CASE WHEN site_code IN (
                'SAMSUNG_SDS_CHUNCHEON','SAMSUNG_SDS_DONGTAN','SAMSUNG_SDS_GUMI'
            ) THEN 'B' ELSE coordinate_quality END,
            geom=CASE site_code
                WHEN 'SAMSUNG_SDS_CHUNCHEON' THEN ST_SetSRID(ST_MakePoint(127.70155799,37.84754135),4326)
                WHEN 'SAMSUNG_SDS_DONGTAN' THEN ST_SetSRID(ST_MakePoint(127.09982382,37.17655615),4326)
                WHEN 'SAMSUNG_SDS_GUMI' THEN ST_SetSRID(ST_MakePoint(128.4139686,36.1081844),4326)
                ELSE geom END,
            commercial_scope_status='IN_SCOPE',
            commercial_model='MANAGED_SERVICE',
            commercial_review_status='CONFIRMED',
            commercial_scope_note='삼성SDS 공식 국내 5개 데이터센터와 기업 고객 대상 클라우드·데이터센터 서비스 확인',
            commercial_source_url='https://www.samsungsds.com/kr/company/global_offices/about_global_offices.html',
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code IN (
            'SAMSUNG_SDS_SANGAM','SAMSUNG_SDS_SUWON','SAMSUNG_SDS_CHUNCHEON',
            'SAMSUNG_SDS_DONGTAN','SAMSUNG_SDS_GUMI'
        )
    """)

    op.execute("""
        UPDATE dc_site SET
            commercial_scope_status='IN_SCOPE', commercial_model='MANAGED_SERVICE',
            commercial_review_status='CONFIRMED',
            commercial_scope_note='LG CNS 공식 자료에서 자체 운영 및 기업 고객 대상 데이터센터 서비스 확인',
            commercial_source_url='https://www.lgcns.com/kr/newsroom/press/detail.ko_0895',
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code IN ('LGCNS_SANGAM','LGCNS_BUSAN','LGCNS_GASAN')
    """)

    op.execute("""
        UPDATE dc_site SET
            commercial_scope_status='IN_SCOPE', commercial_model='COLOCATION',
            commercial_review_status='CONFIRMED',
            commercial_scope_note='코람코 공식 2025년 준공·가동 및 LG유플러스 위탁운영 확인',
            commercial_source_url='https://www.koramco.com/ko/about_02',
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code='KSQUARE_GASAN'
    """)
    op.execute("""
        UPDATE dc_site SET
            commercial_scope_status='IN_SCOPE', commercial_model='WHOLESALE',
            commercial_review_status='CONFIRMED',
            commercial_scope_note='코람코·DCI 공동 개발, 현대건설 본착공, 40MW 상용 AI 데이터센터 공식 발표 확인',
            commercial_source_url='https://www.koramco.com/',
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code='DCI_ANSAN01'
    """)

    op.execute("""
        INSERT INTO dc_project (
            project_code, site_id, project_name, project_type, project_scope,
            status_code, scope_note, review_status, public_visible
        )
        SELECT x.project_code, s.site_id, x.project_name, x.project_type,
               'WHOLE_SITE', x.status_code, x.scope_note, 'CONFIRMED', true
        FROM dc_site s JOIN (VALUES
            ('SAMSUNG_SDS_SANGAM','SAMSUNG_SDS_SANGAM_OP','삼성SDS 상암 데이터센터 운영','CLOUD','OPERATING','기업 고객 대상 데이터센터·클라우드 서비스'),
            ('SAMSUNG_SDS_SUWON','SAMSUNG_SDS_SUWON_OP','삼성SDS 수원 데이터센터 운영','CLOUD','OPERATING','기업 고객 대상 데이터센터·클라우드 서비스'),
            ('SAMSUNG_SDS_GUMI','SAMSUNG_SDS_GUMI_OP','삼성SDS 구미 데이터센터 운영','CLOUD','OPERATING','기업 고객 대상 데이터센터·클라우드 서비스'),
            ('LGCNS_SANGAM','LGCNS_SANGAM_OP','LG CNS 상암 IT센터 운영','COLOCATION','OPERATING','LG CNS 자체 운영 데이터센터'),
            ('LGCNS_GASAN','LGCNS_GASAN_OP','LG CNS 가산 데이터센터 운영','COLOCATION','OPERATING','LG CNS 자체 운영 데이터센터'),
            ('KSQUARE_GASAN','KSQUARE_GASAN_OP','케이스퀘어 데이터센터 가산 운영','COLOCATION','OPERATING','2025년 준공 및 본격 가동'),
            ('DCI_ANSAN01','DCI_ANSAN01_DEV','DCI·코람코 안산 AI 데이터센터 개발','HYPERSCALE','CONSTRUCTION','2026년 6월 현대건설 본착공')
        ) AS x(site_code,project_code,project_name,project_type,status_code,scope_note)
          ON s.site_code=x.site_code
        ON CONFLICT (project_code) DO NOTHING
    """)

    op.execute("""
        INSERT INTO company (
            company_id, standard_name, legal_name, official_url, review_status, note
        ) VALUES
            ('COMP_DCI','DCI Data Centers',NULL,'https://dcidatacenters.com/','CONFIRMED','브룩필드 계열 아시아태평양 상용 데이터센터 운영사')
        ON CONFLICT (company_id) DO NOTHING
    """)

    op.execute("""
        INSERT INTO company_participation (
            company_id, scope_type, scope_id, role_code, review_status,
            confidence_score, evidence_url, public_visible, note
        )
        SELECT x.company_id, 'SITE', s.site_id, x.role_code, 'CONFIRMED', 1.0,
               x.evidence_url, true, '공식 사업자 자료 기준 플레이어 관계 확인'
        FROM dc_site s JOIN (VALUES
            ('SAMSUNG_SDS_SANGAM','ORG-010','OPERATOR','https://www.samsungsds.com/kr/company/global_offices/about_global_offices.html'),
            ('SAMSUNG_SDS_SUWON','ORG-010','OPERATOR','https://www.samsungsds.com/kr/company/global_offices/about_global_offices.html'),
            ('SAMSUNG_SDS_GUMI','ORG-010','OPERATOR','https://www.samsungsds.com/kr/company/global_offices/about_global_offices.html'),
            ('LGCNS_SANGAM','ORG-002','OPERATOR','https://www.lgcns.com/kr/newsroom/press/detail.ko_0895'),
            ('LGCNS_GASAN','ORG-002','OPERATOR','https://www.lgcns.com/kr/newsroom/press/detail.ko_0895'),
            ('KSQUARE_GASAN','ORG-013','ASSET_MANAGER','https://www.koramco.com/ko/about_02'),
            ('KSQUARE_GASAN','ORG-001','OPERATOR','https://m.lguplus.com/about/ko/corporation/promotion/press-kit/detail?atclNo=2000001471'),
            ('DCI_ANSAN01','COMP_DCI','DEVELOPER','https://www.koramco.com/'),
            ('DCI_ANSAN01','COMP_DCI','OPERATOR','https://www.koramco.com/'),
            ('DCI_ANSAN01','ORG-013','ASSET_MANAGER','https://www.koramco.com/'),
            ('DCI_ANSAN01','ORG-017','BUILDER','https://www.koramco.com/')
        ) AS x(site_code,company_id,role_code,evidence_url)
          ON s.site_code=x.site_code
        WHERE NOT EXISTS (
            SELECT 1 FROM company_participation cp
            WHERE cp.company_id=x.company_id AND cp.scope_type='SITE'
              AND cp.scope_id=s.site_id AND cp.role_code=x.role_code
        )
    """)

    op.execute("""
        INSERT INTO capacity_snapshot (
            scope_type, scope_id, capacity_type_code, raw_value, raw_unit,
            raw_phrase, normalized_value_mw, normalized_value, normalized_unit,
            capacity_stage, measurement_basis, document_url, review_status,
            aggregation_excluded, exclusion_reason, note
        )
        SELECT 'PROJECT', p.project_id, 'ANNOUNCED_UNCLASSIFIED_MW',
               '40', 'MW', '40MW 인공지능 데이터센터', 40, 40, 'MW',
               'UNDER_CONSTRUCTION', 'PUBLISHED_CAPACITY',
               'https://www.koramco.com/', 'CONFIRMED', true,
               '공식 발표가 IT Load·수전용량 중 어느 기준인지 명확하지 않아 합산 제외',
               '코람코 공식 회사소식 기준'
        FROM dc_project p WHERE p.project_code='DCI_ANSAN01_DEV'
          AND NOT EXISTS (
              SELECT 1 FROM capacity_snapshot cs
              WHERE cs.scope_type='PROJECT' AND cs.scope_id=p.project_id
                AND cs.capacity_type_code='ANNOUNCED_UNCLASSIFIED_MW'
          )
    """)

    op.execute("""
        INSERT INTO evidence_document (
            source_id, canonical_url, external_document_id, title,
            document_type, publisher, published_at, language_code,
            source_grade, access_scope, review_status, reviewed_by,
            reviewed_at, review_note
        )
        SELECT sr.source_id, x.url, x.external_id, x.title, 'WEB_PAGE',
               x.publisher, x.published_at::timestamptz, 'ko', 'B', 'PUBLIC',
               'CONFIRMED', 'migration-0027', CURRENT_TIMESTAMP,
               '공식 사업자 자료로 센터 운영·상용성·주소 또는 플레이어 관계 확인'
        FROM source_registry sr JOIN (VALUES
            ('SAMSUNG_SDS_NEWS','https://www.samsungsds.com/kr/company/global_offices/about_global_offices.html','official:samsung-sds-korea-dc-locations','삼성SDS 국내 데이터센터 사업장','삼성SDS',NULL),
            ('SAMSUNG_SDS_NEWS','https://www.samsungsds.com/kr/data-center-design-implementation-migration/data-center-design-implementation-migration.html','official:samsung-sds-dc-service','삼성SDS 데이터센터 설계·구축·운영 서비스','삼성SDS',NULL),
            ('LGCNS_NEWS','https://www.lgcns.com/kr/newsroom/press/detail.ko_0895','official:lgcns-owned-operated-dc','LG CNS 데이터센터 재해경감 우수기업 인증','LG CNS',NULL),
            ('KORAMCO_OFFICIAL','https://www.koramco.com/ko/about_02','official:koramco-ksquare-gasan-operation','케이스퀘어 데이터센터 가산 준공 및 본격 가동','코람코',NULL),
            ('KORAMCO_OFFICIAL','https://www.koramco.com/','official:koramco-dci-ansan-groundbreaking','코람코·DCI 안산 40MW AI 데이터센터 착공','코람코','2026-06-09')
        ) AS x(source_code,url,external_id,title,publisher,published_at)
          ON sr.source_code=x.source_code
        WHERE NOT EXISTS (
            SELECT 1 FROM evidence_document ed
            WHERE ed.source_id=sr.source_id AND ed.external_document_id=x.external_id
        )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM evidence_document WHERE external_document_id IN (
            'official:samsung-sds-korea-dc-locations','official:samsung-sds-dc-service',
            'official:lgcns-owned-operated-dc','official:koramco-ksquare-gasan-operation',
            'official:koramco-dci-ansan-groundbreaking'
        )
    """)
    op.execute("""
        DELETE FROM capacity_snapshot WHERE scope_type='PROJECT' AND scope_id IN (
            SELECT project_id FROM dc_project WHERE project_code='DCI_ANSAN01_DEV'
        ) AND note='코람코 공식 회사소식 기준'
    """)
    op.execute("""
        DELETE FROM company_participation
        WHERE note='공식 사업자 자료 기준 플레이어 관계 확인'
    """)
    op.execute("""
        DELETE FROM dc_project WHERE project_code IN (
            'SAMSUNG_SDS_SANGAM_OP','SAMSUNG_SDS_SUWON_OP','SAMSUNG_SDS_GUMI_OP',
            'LGCNS_SANGAM_OP','LGCNS_GASAN_OP','KSQUARE_GASAN_OP','DCI_ANSAN01_DEV'
        )
    """)
    op.execute("""
        UPDATE dc_site SET commercial_scope_status='REVIEW_REQUIRED',
            commercial_model='UNKNOWN', commercial_review_status='NEEDS_EVIDENCE',
            commercial_scope_note=NULL, commercial_source_url=NULL,
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code IN (
            'SAMSUNG_SDS_SANGAM','SAMSUNG_SDS_SUWON','SAMSUNG_SDS_CHUNCHEON',
            'SAMSUNG_SDS_DONGTAN','SAMSUNG_SDS_GUMI','LGCNS_SANGAM','LGCNS_BUSAN',
            'LGCNS_GASAN','KSQUARE_GASAN','DCI_ANSAN01'
        )
    """)
    op.execute("""
        UPDATE dc_site SET
            address_standard=CASE site_code
                WHEN 'SAMSUNG_SDS_CHUNCHEON' THEN '강원특별자치도 춘천시'
                WHEN 'SAMSUNG_SDS_DONGTAN' THEN '경기도 화성시 동탄'
                WHEN 'SAMSUNG_SDS_GUMI' THEN '경상북도 구미시 1공단로 244' END,
            location_precision=CASE site_code
                WHEN 'SAMSUNG_SDS_CHUNCHEON' THEN 'CITY'
                WHEN 'SAMSUNG_SDS_DONGTAN' THEN 'DISTRICT'
                WHEN 'SAMSUNG_SDS_GUMI' THEN 'ROAD' END,
            coordinate_quality=CASE site_code
                WHEN 'SAMSUNG_SDS_CHUNCHEON' THEN 'C'
                WHEN 'SAMSUNG_SDS_DONGTAN' THEN 'C'
                WHEN 'SAMSUNG_SDS_GUMI' THEN 'B' END,
            geom=CASE site_code
                WHEN 'SAMSUNG_SDS_CHUNCHEON' THEN ST_SetSRID(ST_MakePoint(127.7298,37.8813),4326)
                WHEN 'SAMSUNG_SDS_DONGTAN' THEN ST_SetSRID(ST_MakePoint(127.098,37.2),4326)
                WHEN 'SAMSUNG_SDS_GUMI' THEN ST_SetSRID(ST_MakePoint(128.3897504,36.1019019),4326) END,
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code IN ('SAMSUNG_SDS_CHUNCHEON','SAMSUNG_SDS_DONGTAN','SAMSUNG_SDS_GUMI')
    """)
    op.execute("""
        DELETE FROM company WHERE company_id='COMP_DCI'
          AND NOT EXISTS (
              SELECT 1 FROM company_participation cp
              WHERE cp.company_id=company.company_id
          )
    """)
    op.execute("""
        DELETE FROM source_feed WHERE feed_code IN (
            'GNEWS_PLAYER_IT_SERVICE','GNEWS_PLAYER_ASSET_MANAGER',
            'GNEWS_PLAYER_GLOBAL_OPERATOR','GNEWS_PLAYER_BUILDER','GNEWS_PLAYER_CAPITAL'
        )
    """)
    op.execute("DELETE FROM source_registry WHERE source_code='KORAMCO_OFFICIAL'")
