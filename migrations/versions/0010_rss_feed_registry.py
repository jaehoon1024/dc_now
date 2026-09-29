"""Add the RSS feed registry and seed verified official feeds.

Revision ID: 0010_rss_feed_registry
Revises: 0009_source_compliance_policy

Only feed metadata is registered here.  Article bodies, images, and charts are
outside the permitted storage scope for this collector stage.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0010_rss_feed_registry"
down_revision: Union[str, None] = "0009_source_compliance_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_feed",
        sa.Column(
            "feed_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_registry.source_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feed_code", sa.String(length=80), nullable=False),
        sa.Column("feed_name", sa.String(length=250), nullable=False),
        sa.Column("feed_url", sa.Text(), nullable=False),
        sa.Column(
            "feed_format",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'AUTO'"),
        ),
        sa.Column(
            "filter_mode",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'KEYWORD_REQUIRED'"),
        ),
        sa.Column(
            "filter_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "storage_policy",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'METADATA_ONLY'"),
        ),
        sa.Column(
            "request_interval_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("15"),
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_item_published_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "consecutive_failure_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "feed_format IN ('AUTO', 'RSS', 'ATOM')",
            name="ck_source_feed_format",
        ),
        sa.CheckConstraint(
            "filter_mode IN ('ALL', 'KEYWORD_REQUIRED', 'MANUAL_REVIEW')",
            name="ck_source_feed_filter_mode",
        ),
        sa.CheckConstraint(
            "storage_policy IN ('METADATA_ONLY', 'URL_ONLY', 'NO_STORAGE')",
            name="ck_source_feed_storage_policy",
        ),
        sa.CheckConstraint(
            "request_interval_seconds >= 1",
            name="ck_source_feed_request_interval",
        ),
        sa.CheckConstraint(
            "consecutive_failure_count >= 0",
            name="ck_source_feed_failure_count",
        ),
        sa.UniqueConstraint(
            "source_id",
            "feed_code",
            name="uq_source_feed_source_code",
        ),
        sa.UniqueConstraint("feed_url", name="uq_source_feed_url"),
    )

    op.create_index(
        "idx_source_feed_active_source",
        "source_feed",
        ["active", "source_id"],
        unique=False,
    )
    op.create_index(
        "idx_source_feed_last_success",
        "source_feed",
        ["last_success_at"],
        unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_source_feed_updated_at
        BEFORE UPDATE ON source_feed
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )

    # The Ministry of Science and ICT publishes these addresses on its
    # official RSS guide.  Government feed metadata is enabled for collection.
    op.execute(
        """
        UPDATE source_registry
        SET collection_method = 'RSS',
            collection_policy = 'METADATA_ONLY',
            content_storage_policy = 'METADATA_ONLY',
            terms_review_status = 'ALLOWED',
            api_documentation_url =
                'https://www.msit.go.kr/contents/cont.do?mId=173&mPid=147&sCode=user',
            robots_review_status = 'NOT_APPLICABLE',
            request_interval_seconds = 15,
            allowed_content_scope =
                '공식 RSS의 제목·정규 URL·게시일·발행기관만 저장. 본문·이미지·첨부파일은 저장하지 않음',
            compliance_checked_on = CURRENT_DATE,
            legal_approval_required = false,
            compliance_note =
                '과기정통부 공식 RSS 이용안내에 공개된 피드. 최소 메타데이터 정책으로 활성화',
            active = true,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code = 'MSIT_PRESS'
        """
    )

    # ETNews publishes these addresses on its official RSS page.  Because the
    # copyright notice remains in force, only minimum metadata is collected.
    op.execute(
        """
        UPDATE source_registry
        SET collection_method = 'RSS',
            collection_policy = 'METADATA_ONLY',
            content_storage_policy = 'METADATA_ONLY',
            terms_review_status = 'LIMITED',
            api_documentation_url = 'https://www.etnews.com/rss/',
            robots_review_status = 'NOT_APPLICABLE',
            request_interval_seconds = 20,
            allowed_content_scope =
                '공식 RSS의 제목·정규 URL·게시일·발행기관만 저장. 본문·요약문·사진·도표는 저장하지 않음',
            compliance_checked_on = CURRENT_DATE,
            legal_approval_required = true,
            compliance_note =
                '공식 RSS 주소만 사용하며 내부 검토용 메타데이터로 제한. 외부 재배포 전 법무 검토 필요',
            active = true,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code = 'ETNEWS'
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
            feed.feed_code,
            feed.feed_name,
            feed.feed_url,
            'AUTO',
            'KEYWORD_REQUIRED',
            '["데이터센터", "데이터 센터", "IDC", "AIDC", "AI 데이터센터", "클라우드 센터", "전산센터", "서버팜", "하이퍼스케일", "코로케이션", "전력 인프라", "액침냉각"]'::jsonb,
            'METADATA_ONLY',
            15,
            true,
            '과기정통부 공식 RSS 이용안내에서 확인'
        FROM source_registry
        CROSS JOIN (
            VALUES
                ('MSIT_PRESS_RELEASE', '과기정통부 보도자료', 'https://www.msit.go.kr/user/rss/rss.do?bbsSeqNo=94'),
                ('MSIT_ICT_POLICY', '과기정통부 정보통신 정책', 'https://www.msit.go.kr/user/rss/rss.do?bbsSeqNo=67'),
                ('MSIT_NETWORK_POLICY', '과기정통부 네트워크 정책', 'https://www.msit.go.kr/user/rss/rss.do?bbsSeqNo=68')
        ) AS feed(feed_code, feed_name, feed_url)
        WHERE source_code = 'MSIT_PRESS'
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
            feed.feed_code,
            feed.feed_name,
            feed.feed_url,
            'RSS',
            'KEYWORD_REQUIRED',
            '["데이터센터", "데이터 센터", "IDC", "AIDC", "AI 데이터센터", "클라우드 센터", "전산센터", "서버팜", "하이퍼스케일", "코로케이션", "전력 인프라", "액침냉각"]'::jsonb,
            'METADATA_ONLY',
            20,
            true,
            '전자신문 공식 RSS 페이지에서 확인. 기사 본문은 저장하지 않음'
        FROM source_registry
        CROSS JOIN (
            VALUES
                ('ETNEWS_IT', '전자신문 IT', 'http://rss.etnews.com/03.xml'),
                ('ETNEWS_TELECOM', '전자신문 통신', 'http://rss.etnews.com/03033.xml'),
                ('ETNEWS_AI', '전자신문 AI', 'http://rss.etnews.com/04046.xml')
        ) AS feed(feed_code, feed_name, feed_url)
        WHERE source_code = 'ETNEWS'
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_source_feed_updated_at ON source_feed")
    op.drop_index("idx_source_feed_last_success", table_name="source_feed")
    op.drop_index("idx_source_feed_active_source", table_name="source_feed")
    op.drop_table("source_feed")

    op.execute(
        """
        UPDATE source_registry
        SET collection_method = 'HTML',
            terms_review_status = 'PENDING',
            api_documentation_url = NULL,
            robots_review_status = 'NOT_REVIEWED',
            legal_approval_required = true,
            active = false,
            compliance_note =
                'RSS 피드 등록 마이그레이션이 되돌려져 자동수집을 비활성화함',
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code IN ('MSIT_PRESS', 'ETNEWS')
        """
    )
