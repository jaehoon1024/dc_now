"""Register the public Korea data-center directory used for target discovery.

Revision ID: 0020_datacenter_directory_source
Revises: 0019_industry_feeds
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = "0020_datacenter_directory_source"
down_revision: Union[str, None] = "0019_industry_feeds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO source_registry (
            source_code, source_name, source_type, base_url,
            default_source_grade, collection_method, collection_interval,
            terms_review_status, owner_name, active, note,
            collection_policy, content_storage_policy, robots_url,
            robots_review_status, request_interval_seconds,
            allowed_content_scope, compliance_checked_on,
            legal_approval_required, compliance_note
        ) VALUES (
            'DATACENTERMAP_KR', 'Data Center Map 대한민국 시설 디렉터리',
            'INDUSTRY', 'https://www.datacentermap.com/south-korea/',
            'C', 'MANUAL', 'MONTHLY', 'LIMITED', 'Data Center Map', true,
            '국내 데이터센터 후보 발굴 및 공식 출처 교차검증용',
            'METADATA_ONLY', 'METADATA_ONLY',
            'https://www.datacentermap.com/robots.txt', 'NOT_REVIEWED', 60,
            '공개 목록의 시설명·운영사·주소·원문 URL만 후보 메타데이터로 기록',
            CURRENT_DATE, true,
            '후보는 NEEDS_EVIDENCE·비공개로 반입하고 공식 사업자 자료 확인 후 공개'
        ) ON CONFLICT (source_code) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM evidence_document
        WHERE source_id = (
            SELECT source_id FROM source_registry
            WHERE source_code='DATACENTERMAP_KR'
        )
    """)
    op.execute("DELETE FROM source_registry WHERE source_code='DATACENTERMAP_KR'")
