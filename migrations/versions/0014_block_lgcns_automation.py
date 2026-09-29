"""Block automated LG CNS newsroom collection per robots policy.

Revision ID: 0014_block_lgcns_automation
Revises: 0013_skb_press_page

The public newsroom client uses /bin/cf/fetch, while the official robots.txt
disallows /bin/.  No alternate detail-page crawl is enabled.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0014_block_lgcns_automation"
down_revision: Union[str, None] = "0013_skb_press_page"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE source_registry
        SET collection_method = 'HTML',
            collection_policy = 'BLOCKED',
            content_storage_policy = 'NO_STORAGE',
            terms_review_status = 'PENDING',
            robots_url = 'https://www.lgcns.com/robots.txt',
            robots_review_status = 'DISALLOWED',
            allowed_content_scope =
                '자동수집 금지. 담당자가 공식 페이지를 직접 확인하고 출처 URL만 수동 등록',
            compliance_checked_on = CURRENT_DATE,
            legal_approval_required = true,
            compliance_note =
                '공개 뉴스룸이 사용하는 /bin/cf/fetch 경로가 공식 robots.txt의 /bin/ 차단 범위에 포함됨. 상세 페이지 반복 호출 등 우회 수집도 금지',
            active = false,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code = 'LGCNS_NEWS'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE source_registry
        SET collection_policy = 'METADATA_ONLY',
            content_storage_policy = 'URL_ONLY',
            terms_review_status = 'PENDING',
            robots_url = NULL,
            robots_review_status = 'NOT_REVIEWED',
            allowed_content_scope = NULL,
            compliance_checked_on = CURRENT_DATE,
            legal_approval_required = true,
            compliance_note =
                'LG CNS 자동수집 차단 마이그레이션이 되돌려짐. 재검토 전까지 비활성 유지',
            active = false,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code = 'LGCNS_NEWS'
        """
    )
