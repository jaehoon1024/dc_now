"""Add verified commercial data-center development projects.

Revision ID: 0026_commercial_development
Revises: 0025_commercial_source_catalog
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0026_commercial_development"
down_revision: Union[str, None] = "0025_commercial_source_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dc_project",
        sa.Column("planned_rfs_precision", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "dc_project",
        sa.Column("planned_rfs_period", sa.String(length=20), nullable=True),
    )
    op.create_check_constraint(
        "ck_dc_project_rfs_precision",
        "dc_project",
        "planned_rfs_precision IS NULL OR planned_rfs_precision IN "
        "('DAY','MONTH','QUARTER','YEAR','UNKNOWN')",
    )

    op.execute("""
        UPDATE dc_site SET
            commercial_scope_status='IN_SCOPE',
            commercial_model='WHOLESALE',
            commercial_review_status='CONFIRMED',
            commercial_scope_note='Digital Edge 공식 개발·상용 서비스 발표 확인',
            commercial_source_url=CASE site_code
                WHEN 'DIGITALEDGE_SEL3' THEN 'https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-financing-to-complete-major-data-center-campus/'
                WHEN 'DIGITALEDGE_SEL5' THEN 'https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-power-60mw-ansan-data-center/'
            END,
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code IN ('DIGITALEDGE_SEL3','DIGITALEDGE_SEL5')
    """)
    op.execute("""
        UPDATE dc_site SET
            site_name='Princeton Digital SE1 / ESR Bupyeong KR1',
            commercial_scope_status='IN_SCOPE',
            commercial_model='MASTER_LEASE',
            commercial_review_status='CONFIRMED',
            commercial_scope_note='ESR·Wide Creek 개발, PDG 임차·운영 예정 공식 발표 확인',
            commercial_source_url='https://www.esr.com/news/esr-and-wide-creek-amc-to-develop-first-data-centre-in-south-korea/',
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code='PDG_SE1'
    """)

    op.execute("""
        INSERT INTO dc_project (
            project_code, site_id, project_name, project_type, project_scope,
            status_code, scope_note, planned_rfs_date, planned_rfs_precision,
            planned_rfs_period, review_status, public_visible
        )
        SELECT project_code, s.site_id, project_name, 'HYPERSCALE', 'WHOLE_SITE',
               status_code, scope_note, planned_rfs_date::date,
               planned_rfs_precision, planned_rfs_period, 'CONFIRMED', true
        FROM dc_site s
        JOIN (VALUES
            ('DIGITALEDGE_SEL3','DIGITALEDGE_SEL3_DEV','Digital Edge SEL3 개발',
             'CONSTRUCTION','2025년 5월 착공. 공식 목표는 2027년 4분기 RFS이며 날짜는 분기 시작일로 정규화',
             '2027-10-01','QUARTER','2027-Q4'),
            ('DIGITALEDGE_SEL5','DIGITALEDGE_SEL5_DEV','Digital Edge SEL5 개발',
             'SITE_SECURED','90MVA 전력계약이 확보된 안산 부지. 공식 RFS 일정은 미발표',
             NULL,NULL,NULL),
            ('PDG_SE1','PDG_SE1_KR1_DEV','ESR Bupyeong KR1 / PDG SE1 개발',
             'CONSTRUCTION','2025년 11월 착공. 공식 목표는 2028년 운영이며 날짜는 연도 시작일로 정규화',
             '2028-01-01','YEAR','2028')
        ) AS p(site_code,project_code,project_name,status_code,scope_note,
               planned_rfs_date,planned_rfs_precision,planned_rfs_period)
          ON s.site_code=p.site_code
        ON CONFLICT (project_code) DO NOTHING
    """)

    op.execute("""
        INSERT INTO capacity_snapshot (
            scope_type, scope_id, capacity_type_code, raw_value, raw_unit,
            raw_phrase, normalized_value_mw, normalized_value, normalized_unit,
            capacity_stage, measurement_basis, document_url, review_status,
            aggregation_excluded, exclusion_reason, note
        )
        SELECT 'PROJECT', p.project_id, 'ANNOUNCED_UNCLASSIFIED_MW',
               x.mw::text, 'MW', x.raw_phrase, x.mw, x.mw, 'MW',
               x.capacity_stage, 'PUBLISHED_CAPACITY', x.document_url,
               'CONFIRMED', true,
               '공식 발표가 IT Load·수전용량·시설전력 중 어느 기준인지 명확하지 않아 시장 MW 합산에서 제외',
               '공식 사업자 발표 기준'
        FROM dc_project p
        JOIN (VALUES
            ('DIGITALEDGE_SEL3_DEV',60::numeric,'60MW capacity','UNDER_CONSTRUCTION',
             'https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-financing-to-complete-major-data-center-campus/'),
            ('DIGITALEDGE_SEL5_DEV',60::numeric,'60MW hyperscale AI-ready data center','SECURED',
             'https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-power-60mw-ansan-data-center/'),
            ('PDG_SE1_KR1_DEV',80::numeric,'80MW data centre','UNDER_CONSTRUCTION',
             'https://www.esr.com/news/esr-and-wide-creek-amc-to-develop-first-data-centre-in-south-korea/')
        ) AS x(project_code,mw,raw_phrase,capacity_stage,document_url)
          ON p.project_code=x.project_code
    """)
    op.execute("""
        INSERT INTO capacity_snapshot (
            scope_type, scope_id, capacity_type_code, raw_value, raw_unit,
            raw_phrase, normalized_value, normalized_unit, capacity_stage,
            measurement_basis, document_url, review_status,
            aggregation_excluded, exclusion_reason, note
        )
        SELECT 'PROJECT', p.project_id, 'APPARENT_POWER_MVA', '90', 'MVA',
               '90 MVA power agreement', 90, 'MVA', 'SECURED',
               'CONTRACTED',
               'https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-power-60mw-ansan-data-center/',
               'CONFIRMED', true,
               'MVA를 역률 근거 없이 MW로 변환하지 않음',
               'Digital Edge SEL5 공식 전력계약 발표'
        FROM dc_project p WHERE p.project_code='DIGITALEDGE_SEL5_DEV'
    """)

    op.execute("""
        INSERT INTO company (
            company_id, standard_name, legal_name, official_url,
            review_status, note
        ) VALUES
        ('COMP_DIGITAL_EDGE','Digital Edge',NULL,'https://www.digitaledgedc.com/','CONFIRMED','한국 상용 데이터센터 개발·운영사'),
        ('COMP_PDG','Princeton Digital Group',NULL,'https://princetondg.com/','CONFIRMED','Bupyeong KR1 임차·운영 예정'),
        ('COMP_ESR_GROUP','ESR Group',NULL,'https://www.esr.com/','CONFIRMED','Bupyeong KR1 개발 관리자'),
        ('COMP_WIDE_CREEK','Wide Creek Asset Management',NULL,NULL,'CONFIRMED','Bupyeong KR1 공동 개발·자산운용')
        ON CONFLICT (company_id) DO NOTHING
    """)
    op.execute("""
        INSERT INTO company_participation (
            company_id, scope_type, scope_id, role_code, review_status,
            confidence_score, evidence_url, public_visible, note
        )
        SELECT x.company_id, 'SITE', s.site_id, x.role_code, 'CONFIRMED',
               1.0, x.evidence_url, true, '공식 사업자 발표 기준'
        FROM dc_site s
        JOIN (VALUES
            ('DIGITALEDGE_SEL3','COMP_DIGITAL_EDGE','DEVELOPER','https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-financing-to-complete-major-data-center-campus/'),
            ('DIGITALEDGE_SEL3','COMP_DIGITAL_EDGE','OPERATOR','https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-financing-to-complete-major-data-center-campus/'),
            ('DIGITALEDGE_SEL5','COMP_DIGITAL_EDGE','DEVELOPER','https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-power-60mw-ansan-data-center/'),
            ('DIGITALEDGE_SEL5','COMP_DIGITAL_EDGE','OPERATOR','https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-power-60mw-ansan-data-center/'),
            ('PDG_SE1','COMP_ESR_GROUP','DEVELOPER','https://www.esr.com/news/esr-and-wide-creek-amc-to-develop-first-data-centre-in-south-korea/'),
            ('PDG_SE1','COMP_WIDE_CREEK','ASSET_MANAGER','https://www.esr.com/news/esr-and-wide-creek-amc-to-develop-first-data-centre-in-south-korea/'),
            ('PDG_SE1','COMP_PDG','OPERATOR','https://www.esr.com/news/esr-and-wide-creek-amc-to-develop-first-data-centre-in-south-korea/'),
            ('PDG_SE1','COMP_PDG','TENANT','https://www.esr.com/news/esr-and-wide-creek-amc-to-develop-first-data-centre-in-south-korea/')
        ) AS x(site_code,company_id,role_code,evidence_url)
          ON s.site_code=x.site_code
    """)

    op.execute("""
        INSERT INTO evidence_document (
            source_id, canonical_url, external_document_id, title,
            document_type, publisher, published_at, language_code,
            source_grade, access_scope, review_status, reviewed_by,
            reviewed_at, review_note
        )
        SELECT sr.source_id, x.url, x.external_id, x.title,
               'PRESS_RELEASE', x.publisher, x.published_at::timestamptz,
               'en', 'B', 'PUBLIC', 'CONFIRMED', 'migration-0026',
               CURRENT_TIMESTAMP, '공식 사업자 발표로 상용 개발 상태·일정·발표용량 확인'
        FROM source_registry sr
        JOIN (VALUES
            ('DIGITAL_EDGE','https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-financing-to-complete-major-data-center-campus/','official:de-sel3-development','Digital Edge Secures KRW 800B Green Loan for SEL3 Korea','Digital Edge','2025-09-04'),
            ('DIGITAL_EDGE','https://www.digitaledgedc.com/resources/newsroom/digital-edge-secures-power-60mw-ansan-data-center/','official:de-sel5-development','Digital Edge Secures Fully Powered Ansan Data Center Site','Digital Edge','2026-06-08'),
            ('ESR_DC_KR','https://www.esr.com/news/esr-and-wide-creek-amc-to-develop-first-data-centre-in-south-korea/','official:esr-kr1-development','ESR and Wide Creek AMC to Develop First Data Centre in South Korea','ESR','2025-11-17')
        ) AS x(source_code,url,external_id,title,publisher,published_at)
          ON sr.source_code=x.source_code
        WHERE NOT EXISTS (
            SELECT 1 FROM evidence_document ed
            WHERE ed.source_id=sr.source_id AND ed.external_document_id=x.external_id
        )
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM evidence_document
        WHERE external_document_id IN (
            'official:de-sel3-development','official:de-sel5-development',
            'official:esr-kr1-development'
        )
    """)
    op.execute("""
        DELETE FROM company_participation
        WHERE company_id IN (
            'COMP_DIGITAL_EDGE','COMP_PDG','COMP_ESR_GROUP','COMP_WIDE_CREEK'
        ) AND note='공식 사업자 발표 기준'
    """)
    op.execute("""
        DELETE FROM company
        WHERE company_id IN (
            'COMP_DIGITAL_EDGE','COMP_PDG','COMP_ESR_GROUP','COMP_WIDE_CREEK'
        ) AND NOT EXISTS (
            SELECT 1 FROM company_participation cp
            WHERE cp.company_id=company.company_id
        )
    """)
    op.execute("""
        DELETE FROM capacity_snapshot
        WHERE scope_type='PROJECT' AND scope_id IN (
            SELECT project_id FROM dc_project WHERE project_code IN (
                'DIGITALEDGE_SEL3_DEV','DIGITALEDGE_SEL5_DEV','PDG_SE1_KR1_DEV'
            )
        )
    """)
    op.execute("""
        DELETE FROM dc_project WHERE project_code IN (
            'DIGITALEDGE_SEL3_DEV','DIGITALEDGE_SEL5_DEV','PDG_SE1_KR1_DEV'
        )
    """)
    op.execute("""
        UPDATE dc_site SET
            site_name=CASE WHEN site_code='PDG_SE1' THEN 'Princeton Digital SE1' ELSE site_name END,
            commercial_scope_status='REVIEW_REQUIRED',
            commercial_model='UNKNOWN',
            commercial_review_status='NEEDS_EVIDENCE',
            commercial_scope_note=NULL,
            commercial_source_url=NULL,
            updated_at=CURRENT_TIMESTAMP
        WHERE site_code IN ('DIGITALEDGE_SEL3','DIGITALEDGE_SEL5','PDG_SE1')
    """)
    op.drop_constraint("ck_dc_project_rfs_precision", "dc_project", type_="check")
    op.drop_column("dc_project", "planned_rfs_period")
    op.drop_column("dc_project", "planned_rfs_precision")
