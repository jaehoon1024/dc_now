"""Register sources used to expand the data-center discovery queue.

Revision ID: 0021_discovery_sources
Revises: 0020_datacenter_directory_source
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = "0021_discovery_sources"
down_revision: Union[str, None] = "0020_datacenter_directory_source"
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
        ) VALUES
        ('AI_DC_KOREA','AI-DC KOREA 국내 데이터센터 레지스트리','INDUSTRY',
         'https://www.ai-dc.co.kr/data-centers','C','MANUAL','MONTHLY','LIMITED',
         'AI-DC KOREA',true,'후보 시설명·주소·운영 상태 교차검증용',
         'MANUAL_ONLY','URL_ONLY','https://www.ai-dc.co.kr/robots.txt','NOT_REVIEWED',60,
         '공개 검색 결과의 시설 메타데이터와 원문 URL만 수동 확인',CURRENT_DATE,true,
         '후보는 비공개 NEEDS_EVIDENCE로 유지하고 공식 출처 확인 후 공개'),
        ('WORLD_BANK_GREEN_DC','World Bank Greening Digital in Korea','INDUSTRY',
         'https://www.worldbank.org/','B','PDF',NULL,'ALLOWED','World Bank',true,
         '국내 공공·민간 데이터센터 모집단 규모와 부문별 발굴 기준 참고',
         'MANUAL_ONLY','URL_ONLY',NULL,'NOT_APPLICABLE',60,
         '공개 보고서의 집계·분류와 원문 URL만 사용',CURRENT_DATE,false,
         '개별 시설 확정 근거가 아닌 발굴 모집단 참고자료')
        ON CONFLICT (source_code) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""
        DELETE FROM evidence_document WHERE source_id IN (
            SELECT source_id FROM source_registry
            WHERE source_code IN ('AI_DC_KOREA','WORLD_BANK_GREEN_DC')
        )
    """)
    op.execute("DELETE FROM source_registry WHERE source_code IN ('AI_DC_KOREA','WORLD_BANK_GREEN_DC')")
