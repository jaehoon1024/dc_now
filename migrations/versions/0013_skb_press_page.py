"""Register the SK Broadband official press-release list page.

Revision ID: 0013_skb_press_page
Revises: 0012_lgu_newsroom_page
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0013_skb_press_page"
down_revision: Union[str, None] = "0012_lgu_newsroom_page"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE source_registry
        SET collection_method = 'HTML',
            collection_policy = 'METADATA_ONLY',
            content_storage_policy = 'METADATA_ONLY',
            terms_review_status = 'LIMITED',
            robots_url = 'https://www.skbroadband.com/robots.txt',
            robots_review_status = 'PARTIAL',
            request_interval_seconds = 30,
            allowed_content_scope =
                '공식 보도자료 목록의 제목·정규 URL·게시일·발행기관만 저장. 상세 본문·이미지·첨부파일은 요청하거나 저장하지 않음',
            compliance_checked_on = CURRENT_DATE,
            legal_approval_required = true,
            compliance_note =
                '공식 공개 목록 1페이지만 호출하는 내부 검토용 최소 메타데이터 수집. 저작권 고지를 존중하며 외부 재배포 전 별도 검토 필요',
            active = true,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code = 'SKB_IDC'
        """
    )
    op.execute(
        """
        INSERT INTO source_page (
            source_id, page_code, page_name, page_url, parser_code,
            filter_keywords, request_interval_seconds, active, note
        )
        SELECT
            source_id, 'SKB_PRESS', 'SK브로드밴드 공식 보도자료',
            'https://www.skbroadband.com/kor/pr/press_list.do?menu_id=K05010000',
            'SKB_PRESS_V1',
            '["데이터센터", "데이터 센터", "IDC", "AIDC", "AI 데이터센터", "AI DC", "클라우드 센터", "전산센터", "서버팜", "하이퍼스케일", "코로케이션", "전력 인프라", "액침냉각", "GPU 센터"]'::jsonb,
            30, true,
            '공식 보도자료 목록 1페이지만 확인. 상세 본문은 요청하지 않음'
        FROM source_registry
        WHERE source_code = 'SKB_IDC'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM source_page
        WHERE page_code = 'SKB_PRESS'
          AND source_id = (
              SELECT source_id FROM source_registry
              WHERE source_code = 'SKB_IDC'
          )
        """
    )
    op.execute(
        """
        UPDATE source_registry
        SET terms_review_status = 'PENDING',
            content_storage_policy = 'URL_ONLY',
            robots_url = NULL,
            robots_review_status = 'NOT_REVIEWED',
            allowed_content_scope = NULL,
            legal_approval_required = true,
            compliance_note =
                'SK브로드밴드 보도자료 수집 마이그레이션이 되돌려져 자동수집을 비활성화함',
            active = false,
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code = 'SKB_IDC'
        """
    )
