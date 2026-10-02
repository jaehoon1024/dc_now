"""Add broad data-center news discovery feeds.

Revision ID: 0023_news_discovery_feeds
Revises: 0022_dealbook_source
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0023_news_discovery_feeds"
down_revision: Union[str, None] = "0022_dealbook_source"
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
            'GOOGLE_NEWS_DC', 'Google News 데이터센터 탐색', 'NEWS',
            'https://news.google.com/', 'C', 'RSS', 'DAILY', 'LIMITED',
            'Google', true,
            '국내 데이터센터·전력·투자·건설 및 해외 한국 시장 보도 탐색',
            'METADATA_ONLY', 'METADATA_ONLY', NULL, 'NOT_APPLICABLE', 15,
            '공개 RSS의 제목·기사 연결 URL·게시일·실제 발행기관만 저장. 본문·요약·이미지는 저장하지 않음',
            CURRENT_DATE, true,
            '뉴스 탐색용 C등급 메타데이터. 센터 속성 확정에는 공식 1차 자료 교차검증 필요'
        ) ON CONFLICT (source_code) DO UPDATE SET
            active=true, collection_method='RSS', collection_policy='METADATA_ONLY',
            content_storage_policy='METADATA_ONLY', updated_at=CURRENT_TIMESTAMP
    """)
    op.execute("""
        INSERT INTO source_feed (
            source_id, feed_code, feed_name, feed_url, feed_format,
            filter_mode, filter_keywords, storage_policy,
            request_interval_seconds, active, note
        )
        SELECT source_id, feed_code, feed_name, feed_url, 'RSS', 'ALL',
               '[]'::jsonb, 'METADATA_ONLY', 15, true,
               '검색어로 범위를 제한한 뉴스 메타데이터 탐색 피드'
        FROM source_registry
        CROSS JOIN (VALUES
            ('GNEWS_DC_CORE', '국내 데이터센터 보도',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+when%3A90d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_AI_INFRA', 'AI·GPU 데이터센터 보도',
             'https://news.google.com/rss/search?q=%28%22AI+%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+OR+AIDC+OR+%22GPU+%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22%29+when%3A180d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_DC_POWER', '데이터센터 전력·계통 보도',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%EC%A0%84%EB%A0%A5+OR+%EC%A0%84%EB%A0%A5%EA%B3%84%ED%86%B5+OR+%EB%B3%80%EC%A0%84%EC%86%8C+OR+%EC%88%98%EC%A0%84%29+when%3A180d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_DC_FINANCE', '데이터센터 투자·PF·리츠 보도',
             'https://news.google.com/rss/search?q=%22%EB%8D%B0%EC%9D%B4%ED%84%B0%EC%84%BC%ED%84%B0%22+%28%ED%88%AC%EC%9E%90+OR+PF+OR+%EB%A6%AC%EC%B8%A0+OR+%EC%9E%90%EC%82%B0%EC%9A%B4%EC%9A%A9+OR+%EB%A7%A4%EA%B0%81%29+when%3A180d&hl=ko&gl=KR&ceid=KR%3Ako'),
            ('GNEWS_KOREA_GLOBAL', '해외 매체의 한국 데이터센터 보도',
             'https://news.google.com/rss/search?q=%22South+Korea%22+%22data+center%22+when%3A180d&hl=en-US&gl=US&ceid=US%3Aen')
        ) AS feeds(feed_code, feed_name, feed_url)
        WHERE source_code='GOOGLE_NEWS_DC'
        ON CONFLICT (feed_url) DO UPDATE SET active=true, updated_at=CURRENT_TIMESTAMP
    """)
    op.execute("""
        UPDATE source_feed
        SET filter_keywords = (
            SELECT jsonb_agg(DISTINCT value)
            FROM jsonb_array_elements_text(
                filter_keywords || '[
                    "AI DC", "GPU 데이터센터", "GPU 센터", "GPU 클러스터",
                    "HPC", "서버팜", "하이퍼스케일", "코로케이션",
                    "클라우드 리전", "가용영역", "전력계통", "계통영향평가",
                    "수전용량", "액침냉각", "수랭", "PUE", "DCIM"
                ]'::jsonb
            ) AS value
        ), updated_at=CURRENT_TIMESTAMP
        WHERE filter_mode='KEYWORD_REQUIRED'
    """)


def downgrade() -> None:
    op.execute("DELETE FROM source_feed WHERE feed_code LIKE 'GNEWS_%'")
    op.execute("""
        DELETE FROM evidence_document WHERE source_id=(
            SELECT source_id FROM source_registry WHERE source_code='GOOGLE_NEWS_DC'
        )
    """)
    op.execute("DELETE FROM source_registry WHERE source_code='GOOGLE_NEWS_DC'")
