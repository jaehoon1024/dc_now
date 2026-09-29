"""Register the LG Uplus official press-room HTML page.

Revision ID: 0012_lgu_newsroom_page
Revises: 0011_ktcloud_rss_feed
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0012_lgu_newsroom_page"
down_revision: Union[str, None] = "0011_ktcloud_rss_feed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_page",
        sa.Column(
            "page_id",
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
        sa.Column("page_code", sa.String(length=80), nullable=False),
        sa.Column("page_name", sa.String(length=250), nullable=False),
        sa.Column("page_url", sa.Text(), nullable=False),
        sa.Column("parser_code", sa.String(length=80), nullable=False),
        sa.Column(
            "filter_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "request_interval_seconds", sa.Integer(), nullable=False,
            server_default=sa.text("30"),
        ),
        sa.Column(
            "active", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "consecutive_failure_count", sa.Integer(), nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "request_interval_seconds >= 1",
            name="ck_source_page_request_interval",
        ),
        sa.CheckConstraint(
            "consecutive_failure_count >= 0",
            name="ck_source_page_failure_count",
        ),
        sa.UniqueConstraint(
            "source_id", "page_code", name="uq_source_page_source_code"
        ),
        sa.UniqueConstraint("page_url", name="uq_source_page_url"),
    )
    op.create_index(
        "idx_source_page_active_source", "source_page",
        ["active", "source_id"], unique=False,
    )
    op.execute(
        """
        CREATE TRIGGER trg_source_page_updated_at
        BEFORE UPDATE ON source_page
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )
    op.execute(
        """
        UPDATE source_registry
        SET collection_method = 'HTML',
            collection_policy = 'METADATA_ONLY',
            content_storage_policy = 'METADATA_ONLY',
            terms_review_status = 'LIMITED',
            terms_url = 'https://news.lguplus.com/뉴스룸-콘텐츠-이용-안내',
            robots_url = 'https://news.lguplus.com/robots.txt',
            robots_review_status = 'PARTIAL',
            request_interval_seconds = 30,
            allowed_content_scope =
                '공식 보도자료 목록의 제목·정규 URL·게시일·발행기관만 저장. 본문·이미지·영상·첨부파일은 저장하지 않음',
            compliance_checked_on = CURRENT_DATE,
            legal_approval_required = true,
            compliance_note =
                '뉴스룸 이용정책의 비영리·출처표시·변경금지 조건 적용. 내부 검토용 최소 메타데이터로 제한하며 외부 재배포 전 별도 검토 필요',
            active = true,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code = 'LGU_NEWS'
        """
    )
    op.execute(
        """
        INSERT INTO source_page (
            source_id, page_code, page_name, page_url, parser_code,
            filter_keywords, request_interval_seconds, active, note
        )
        SELECT
            source_id, 'LGU_PRESS', 'LG유플러스 공식 보도자료',
            'https://news.lguplus.com/', 'LGUPLUS_PRESS_V1',
            '["데이터센터", "데이터 센터", "IDC", "AIDC", "AI 데이터센터", "AI DC", "클라우드 센터", "전산센터", "서버팜", "하이퍼스케일", "코로케이션", "전력 인프라", "액침냉각", "GPU 센터"]'::jsonb,
            30, true,
            '공식 뉴스룸 첫 화면의 프레스센터 보도자료 목록만 수집'
        FROM source_registry
        WHERE source_code = 'LGU_NEWS'
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_source_page_updated_at ON source_page")
    op.drop_index("idx_source_page_active_source", table_name="source_page")
    op.drop_table("source_page")
    op.execute(
        """
        UPDATE source_registry
        SET terms_review_status = 'PENDING',
            content_storage_policy = 'URL_ONLY',
            terms_url = NULL,
            robots_url = NULL,
            robots_review_status = 'NOT_REVIEWED',
            allowed_content_scope = NULL,
            legal_approval_required = true,
            compliance_note =
                'LG유플러스 HTML 수집 마이그레이션이 되돌려져 자동수집을 비활성화함',
            active = false,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code = 'LGU_NEWS'
        """
    )
