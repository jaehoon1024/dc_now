"""Register DealBook News as a filtered metadata-only RSS source.

Revision ID: 0022_dealbook_source
Revises: 0021_discovery_sources
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op

revision: str = "0022_dealbook_source"
down_revision: Union[str, None] = "0021_discovery_sources"
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
            'DEALBOOK_NEWS', '딜북뉴스', 'NEWS',
            'https://www.dealbook.co.kr/', 'C', 'RSS', 'DAILY', 'LIMITED',
            '딜북뉴스', true,
            '데이터센터 PF·투자·자산운용·시공·개발 동향의 후보 근거',
            'METADATA_ONLY', 'METADATA_ONLY',
            'https://www.dealbook.co.kr/robots.txt', 'ALLOWED', 30,
            '공개 RSS에서 데이터센터 관련 제목·정규 URL·게시일·발행기관만 저장. 본문·요약·이미지는 저장하지 않음',
            CURRENT_DATE, true,
            'robots.txt의 /bluedot/ 및 /p/ 차단 경로는 요청하지 않음. 2차 보도자료이므로 공식 출처 교차검증 후 공개'
        ) ON CONFLICT (source_code) DO NOTHING
    """)
    op.execute("""
        INSERT INTO source_feed (
            source_id, feed_code, feed_name, feed_url, feed_format,
            filter_mode, filter_keywords, storage_policy,
            request_interval_seconds, active, note
        )
        SELECT source_id, 'DEALBOOK_DC', '딜북뉴스 데이터센터 태그',
               'https://www.dealbook.co.kr/tag/deiteosenteo/rss/', 'RSS',
               'ALL', '[]'::jsonb,
               'METADATA_ONLY', 30, true,
               '공개 데이터센터 태그 RSS. 기사 본문·요약·이미지는 저장하지 않음'
        FROM source_registry WHERE source_code='DEALBOOK_NEWS'
        ON CONFLICT (feed_url) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM source_feed WHERE feed_code='DEALBOOK_DC'")
    op.execute("""
        DELETE FROM evidence_document WHERE source_id=(
            SELECT source_id FROM source_registry WHERE source_code='DEALBOOK_NEWS'
        )
    """)
    op.execute("DELETE FROM source_registry WHERE source_code='DEALBOOK_NEWS'")
