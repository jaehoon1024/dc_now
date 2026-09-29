"""Enable the official KT Cloud technology blog RSS feed.

Revision ID: 0011_ktcloud_rss_feed
Revises: 0010_rss_feed_registry

The feed is exposed by the official KT Cloud technology blog.  Collection is
limited to title, canonical URL, publication time, and publisher metadata.
Article bodies, summaries, images, and attachments are not stored.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0011_ktcloud_rss_feed"
down_revision: Union[str, None] = "0010_rss_feed_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE source_registry
        SET collection_method = 'RSS',
            collection_policy = 'METADATA_ONLY',
            content_storage_policy = 'METADATA_ONLY',
            terms_review_status = 'LIMITED',
            api_documentation_url = 'https://tech.ktcloud.com/',
            robots_url = 'https://tech.ktcloud.com/robots.txt',
            robots_review_status = 'PARTIAL',
            request_interval_seconds = 20,
            allowed_content_scope =
                '공식 RSS의 제목·정규 URL·게시일·발행기관만 저장. 본문·요약문·이미지·첨부파일은 저장하지 않음',
            compliance_checked_on = CURRENT_DATE,
            legal_approval_required = true,
            compliance_note =
                'KT Cloud 공식 기술 블로그가 제공하는 RSS만 사용. 내부 검토용 최소 메타데이터로 제한하며 외부 재배포 전 별도 검토 필요',
            active = true,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code = 'KT_CLOUD_PRESS'
        """
    )

    op.execute(
        """
        INSERT INTO source_feed (
            source_id,
            feed_code,
            feed_name,
            feed_url,
            feed_format,
            filter_mode,
            filter_keywords,
            storage_policy,
            request_interval_seconds,
            active,
            note
        )
        SELECT
            source_id,
            'KT_CLOUD_TECH',
            'KT Cloud 기술 블로그',
            'https://ktcloudplatform.tistory.com/rss',
            'RSS',
            'KEYWORD_REQUIRED',
            '["데이터센터", "데이터 센터", "IDC", "AIDC", "AI 데이터센터", "AI DC", "클라우드 센터", "전산센터", "서버팜", "하이퍼스케일", "코로케이션", "전력 인프라", "액침냉각", "GPU 센터"]'::jsonb,
            'METADATA_ONLY',
            20,
            true,
            'KT Cloud 공식 기술 블로그가 공개한 RSS. 기사 본문과 이미지는 저장하지 않음'
        FROM source_registry
        WHERE source_code = 'KT_CLOUD_PRESS'
        ON CONFLICT (feed_url) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM source_feed
        WHERE feed_code = 'KT_CLOUD_TECH'
          AND source_id = (
              SELECT source_id
              FROM source_registry
              WHERE source_code = 'KT_CLOUD_PRESS'
          )
        """
    )

    op.execute(
        """
        UPDATE source_registry
        SET collection_method = 'HTML',
            collection_policy = 'METADATA_ONLY',
            content_storage_policy = 'URL_ONLY',
            terms_review_status = 'PENDING',
            api_documentation_url = NULL,
            robots_url = NULL,
            robots_review_status = 'NOT_REVIEWED',
            allowed_content_scope = NULL,
            legal_approval_required = true,
            compliance_note =
                'KT Cloud RSS 확장 마이그레이션이 되돌려져 자동수집을 비활성화함',
            active = false,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code = 'KT_CLOUD_PRESS'
        """
    )
