"""Apply conservative source collection and copyright controls.

Revision ID: 0009_source_compliance_policy
Revises: 0008_seed_sources
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0009_source_compliance_policy"
down_revision: Union[str, None] = "0008_seed_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


API_SOURCES = {
    "OPENDART": {
        "terms_status": "ALLOWED",
        "active": True,
        "interval": 1,
        "daily_limit": 19000,
        "terms_url": "https://opendart.fss.or.kr/intro/terms.do",
        "api_url": "https://opendart.fss.or.kr/guide/main.do",
        "scope": "공식 API 응답과 원문 파일. 인증키는 환경변수로만 관리",
        "note": "공식 API만 사용. 일반적으로 20,000건 이상 요청 시 제한되므로 내부 상한을 19,000건으로 설정",
    },
    "DATA_GO_KR_BUILDING": {
        "terms_status": "LIMITED",
        "active": False,
        "interval": 5,
        "daily_limit": None,
        "terms_url": "https://www.data.go.kr/ugs/selectPublicDataUseGuideView.do",
        "api_url": "https://www.data.go.kr/",
        "scope": "활용신청한 API 응답. 각 데이터셋의 이용허락범위를 별도로 확인",
        "note": "사용할 건축물·인허가 데이터셋을 확정하고 인증키를 등록한 뒤 활성화",
    },
    "LOCALDATA": {
        "terms_status": "PENDING",
        "active": False,
        "interval": 5,
        "daily_limit": None,
        "terms_url": None,
        "api_url": "https://www.localdata.go.kr/",
        "scope": "공식 제공 파일 또는 API 응답만 허용",
        "note": "세부 이용조건과 호출 제한을 담당자가 확인하기 전까지 비활성화",
    },
    "KEPCO_OPEN_DATA": {
        "terms_status": "PENDING",
        "active": False,
        "interval": 5,
        "daily_limit": None,
        "terms_url": None,
        "api_url": "https://bigdata.kepco.co.kr/",
        "scope": "승인받은 전력데이터 상품 또는 API 응답만 허용",
        "note": "데이터 상품별 이용조건·비용·재배포 범위를 확인한 뒤 활성화",
    },
}


MANUAL_SOURCES = (
    "EAIS",
    "LAW_GO_KR",
    "KPX_EPSIS",
    "EUM",
)


METADATA_SOURCES = (
    "MOTIE_PRESS",
    "MOLIT_PRESS",
    "MSIT_PRESS",
    "LGU_IDC",
    "LGU_NEWS",
    "LGCNS_NEWS",
    "SKB_IDC",
    "KT_CLOUD_PRESS",
    "NAVER_CLOUD",
    "NHN_INSIDE",
    "KINX",
    "EQUINIX_NEWS",
    "DIGITAL_REALTY_NEWS",
    "KDCC",
    "UPTIME_INSTITUTE",
    "DCD",
    "ETNEWS",
    "YONHAP",
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join("'" + value.replace("'", "''") + "'" for value in values)


def upgrade() -> None:
    op.add_column(
        "source_registry",
        sa.Column(
            "collection_policy",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
    )
    op.add_column(
        "source_registry",
        sa.Column(
            "content_storage_policy",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'URL_ONLY'"),
        ),
    )
    op.add_column(
        "source_registry",
        sa.Column("terms_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "source_registry",
        sa.Column("api_documentation_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "source_registry",
        sa.Column("robots_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "source_registry",
        sa.Column(
            "robots_review_status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'NOT_REVIEWED'"),
        ),
    )
    op.add_column(
        "source_registry",
        sa.Column(
            "request_interval_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("10"),
        ),
    )
    op.add_column(
        "source_registry",
        sa.Column("daily_request_limit", sa.Integer(), nullable=True),
    )
    op.add_column(
        "source_registry",
        sa.Column("allowed_content_scope", sa.Text(), nullable=True),
    )
    op.add_column(
        "source_registry",
        sa.Column("compliance_checked_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "source_registry",
        sa.Column(
            "legal_approval_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "source_registry",
        sa.Column("compliance_note", sa.Text(), nullable=True),
    )

    op.create_check_constraint(
        "ck_source_registry_collection_policy",
        "source_registry",
        "collection_policy IN ('OFFICIAL_API', 'METADATA_ONLY', "
        "'MANUAL_ONLY', 'BLOCKED', 'PENDING')",
    )
    op.create_check_constraint(
        "ck_source_registry_storage_policy",
        "source_registry",
        "content_storage_policy IN ('API_RESPONSE', 'METADATA_ONLY', "
        "'URL_ONLY', 'NO_STORAGE')",
    )
    op.create_check_constraint(
        "ck_source_registry_robots_status",
        "source_registry",
        "robots_review_status IN ('NOT_REVIEWED', 'ALLOWED', 'PARTIAL', "
        "'DISALLOWED', 'NOT_APPLICABLE')",
    )
    op.create_check_constraint(
        "ck_source_registry_request_interval",
        "source_registry",
        "request_interval_seconds >= 1",
    )
    op.create_check_constraint(
        "ck_source_registry_daily_limit",
        "source_registry",
        "daily_request_limit IS NULL OR daily_request_limit >= 1",
    )

    # Safe default: disable everything before applying source-specific policy.
    op.execute(
        """
        UPDATE source_registry
        SET active = false,
            collection_policy = 'PENDING',
            content_storage_policy = 'URL_ONLY',
            robots_review_status = 'NOT_REVIEWED',
            legal_approval_required = true,
            compliance_checked_on = CURRENT_DATE,
            updated_at = CURRENT_TIMESTAMP
        """
    )

    for source_code, policy in API_SOURCES.items():
        bind = op.get_bind()
        bind.execute(
            sa.text(
                """
                UPDATE source_registry
                SET collection_policy = 'OFFICIAL_API',
                    content_storage_policy = 'API_RESPONSE',
                    terms_review_status = :terms_status,
                    terms_url = :terms_url,
                    api_documentation_url = :api_url,
                    robots_review_status = 'NOT_APPLICABLE',
                    request_interval_seconds = :request_interval,
                    daily_request_limit = :daily_limit,
                    allowed_content_scope = :scope,
                    active = :active,
                    legal_approval_required = :legal_required,
                    compliance_note = :note,
                    updated_at = CURRENT_TIMESTAMP
                WHERE source_code = :source_code
                """
            ),
            {
                "source_code": source_code,
                "terms_status": policy["terms_status"],
                "terms_url": policy["terms_url"],
                "api_url": policy["api_url"],
                "request_interval": policy["interval"],
                "daily_limit": policy["daily_limit"],
                "scope": policy["scope"],
                "active": policy["active"],
                "legal_required": source_code != "OPENDART",
                "note": policy["note"],
            },
        )

    op.execute(
        f"""
        UPDATE source_registry
        SET collection_policy = 'MANUAL_ONLY',
            content_storage_policy = 'URL_ONLY',
            collection_method = 'MANUAL',
            request_interval_seconds = 30,
            allowed_content_scope =
                '담당자가 화면에서 확인한 사실값·URL·확인일만 입력. 원문·이미지 저장 금지',
            compliance_note =
                '로그인·본인확인·자동수집 제한 가능성이 있어 자동수집을 금지하고 수동 확인만 허용',
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code IN ({_quoted(MANUAL_SOURCES)})
        """
    )

    op.execute(
        f"""
        UPDATE source_registry
        SET collection_policy = 'METADATA_ONLY',
            content_storage_policy = 'METADATA_ONLY',
            request_interval_seconds = 15,
            allowed_content_scope =
                '제목·정규 URL·게시일·발행기관·자체 작성 요약만 저장. 본문·사진·도표 복제 금지',
            compliance_note =
                'robots.txt와 사이트 이용약관을 별도 승인하기 전까지 최소 메타데이터 정책 적용',
            updated_at = CURRENT_TIMESTAMP
        WHERE source_code IN ({_quoted(METADATA_SOURCES)})
        """
    )

    # Store a robots.txt check target without claiming that the rule was reviewed.
    op.execute(
        """
        UPDATE source_registry
        SET robots_url = regexp_replace(base_url, '^(https?://[^/]+).*$', '\\1/robots.txt')
        WHERE base_url IS NOT NULL
          AND collection_policy IN ('METADATA_ONLY', 'MANUAL_ONLY')
        """
    )

    op.execute(
        """
        CREATE VIEW v_source_collection_readiness AS
        SELECT
            source_id,
            source_code,
            source_name,
            source_type,
            default_source_grade,
            collection_method,
            collection_interval,
            collection_policy,
            content_storage_policy,
            terms_review_status,
            robots_review_status,
            request_interval_seconds,
            daily_request_limit,
            legal_approval_required,
            active,
            CASE
                WHEN active = false THEN 'DISABLED'
                WHEN terms_review_status NOT IN ('ALLOWED', 'LIMITED') THEN 'TERMS_REVIEW_REQUIRED'
                WHEN collection_policy = 'PENDING' THEN 'POLICY_REQUIRED'
                WHEN collection_policy = 'BLOCKED' THEN 'BLOCKED'
                ELSE 'READY'
            END AS readiness_status,
            allowed_content_scope,
            compliance_checked_on,
            compliance_note,
            updated_at
        FROM source_registry
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_source_collection_readiness")

    op.drop_constraint(
        "ck_source_registry_daily_limit", "source_registry", type_="check"
    )
    op.drop_constraint(
        "ck_source_registry_request_interval", "source_registry", type_="check"
    )
    op.drop_constraint(
        "ck_source_registry_robots_status", "source_registry", type_="check"
    )
    op.drop_constraint(
        "ck_source_registry_storage_policy", "source_registry", type_="check"
    )
    op.drop_constraint(
        "ck_source_registry_collection_policy", "source_registry", type_="check"
    )

    for column_name in (
        "compliance_note",
        "legal_approval_required",
        "compliance_checked_on",
        "allowed_content_scope",
        "daily_request_limit",
        "request_interval_seconds",
        "robots_review_status",
        "robots_url",
        "api_documentation_url",
        "terms_url",
        "content_storage_policy",
        "collection_policy",
    ):
        op.drop_column("source_registry", column_name)
