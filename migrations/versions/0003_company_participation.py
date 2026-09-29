"""Create company master, aliases, roles, and participation relations.

Revision ID: 0003_company_participation
Revises: 0002_capacity_schema
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0003_company_participation"
down_revision: Union[str, None] = "0002_capacity_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COMPANIES = (
    (
        "ORG-001",
        "LG유플러스",
        "㈜엘지유플러스",
        "220-81-39938",
        "https://www.lguplus.com/",
    ),
    (
        "ORG-002",
        "LG CNS",
        "주식회사 엘지씨엔에스",
        "116-81-19477",
        "https://www.lgcns.com/",
    ),
    (
        "ORG-003",
        "SK브로드밴드",
        "SK브로드밴드(주)",
        "214-86-18758",
        "https://biz.skbroadband.com/",
    ),
    (
        "ORG-004",
        "kt cloud",
        "주식회사 케이티클라우드",
        "696-87-02611",
        "https://www.ktcloud.com/",
    ),
    (
        "ORG-005",
        "네이버클라우드",
        "네이버클라우드 주식회사",
        None,
        "https://www.navercloudcorp.com/",
    ),
    (
        "ORG-006",
        "NHN클라우드",
        "엔에이치엔클라우드(주)",
        "424-88-02352",
        "https://www.nhncloud.com/",
    ),
    (
        "ORG-007",
        "KINX",
        "(주)케이아이엔엑스",
        "101-81-59273",
        "https://www.kinx.net/",
    ),
)


ALIASES = (
    ("ORG-001", "LG U+", "lg u+", "BRAND"),
    ("ORG-001", "LG Uplus", "lg uplus", "ENGLISH"),
    ("ORG-001", "LG유플러스", "lg유플러스", "BRAND"),
    ("ORG-001", "엘지유플러스", "엘지유플러스", "LEGAL"),
    ("ORG-001", "유플러스", "유플러스", "BRAND"),
    ("ORG-002", "LG CNS", "lg cns", "BRAND"),
    ("ORG-002", "LG씨엔에스", "lg씨엔에스", "BRAND"),
    ("ORG-002", "엘지씨엔에스", "엘지씨엔에스", "LEGAL"),
    ("ORG-002", "(주)엘지씨엔에스", "엘지씨엔에스", "LEGAL"),
    ("ORG-003", "SK브로드밴드", "sk브로드밴드", "BRAND"),
    ("ORG-003", "SK broadband", "sk broadband", "ENGLISH"),
    ("ORG-003", "SKB", "skb", "ABBREVIATION"),
    ("ORG-004", "kt cloud", "kt cloud", "BRAND"),
    ("ORG-004", "KT Cloud", "kt cloud", "ENGLISH"),
    ("ORG-004", "KT클라우드", "kt클라우드", "BRAND"),
    ("ORG-004", "케이티클라우드", "케이티클라우드", "LEGAL"),
    ("ORG-005", "네이버클라우드", "네이버클라우드", "BRAND"),
    ("ORG-005", "NAVER Cloud", "naver cloud", "ENGLISH"),
    ("ORG-005", "Naver Cloud", "naver cloud", "ENGLISH"),
    ("ORG-006", "NHN Cloud", "nhn cloud", "ENGLISH"),
    ("ORG-006", "NHN클라우드", "nhn클라우드", "BRAND"),
    ("ORG-006", "엔에이치엔클라우드", "엔에이치엔클라우드", "LEGAL"),
    ("ORG-007", "KINX", "kinx", "BRAND"),
    ("ORG-007", "케이아이엔엑스", "케이아이엔엑스", "LEGAL"),
    ("ORG-007", "(주)케이아이엔엑스", "케이아이엔엑스", "LEGAL"),
)


ROLES = (
    ("OWNER", "소유자", "토지·건물·시설의 소유 주체"),
    ("DEVELOPER", "개발사업자", "데이터센터 개발사업의 주체"),
    ("DESIGNER", "설계사", "건축·전기·기계 등 설계 수행사"),
    ("BUILDER", "시공사", "건축·설비 공사를 수행하는 회사"),
    ("OPERATOR", "운영사", "데이터센터 시설을 실제 운영하는 회사"),
    ("DBO_PROVIDER", "DBO 수행사", "설계·구축·운영을 통합 수행하는 회사"),
    ("TENANT", "임차인", "상면·전력·시설을 임차하거나 입주한 고객"),
    ("SELLER", "판매사", "서비스 재판매 또는 영업 채널 역할의 회사"),
)


def upgrade() -> None:
    op.create_table(
        "company",
        sa.Column("company_id", sa.String(length=30), primary_key=True),
        sa.Column("standard_name", sa.String(length=200), nullable=False),
        sa.Column("legal_name", sa.String(length=250), nullable=True),
        sa.Column("business_registration_no", sa.String(length=30), nullable=True),
        sa.Column("official_url", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'CONFIRMED'"),
        ),
        sa.Column(
            "record_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
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
            "review_status IN ('CANDIDATE', 'CONFIRMED', 'CONFLICT', 'REJECTED')",
            name="ck_company_review_status",
        ),
        sa.CheckConstraint(
            "record_status IN ('ACTIVE', 'INACTIVE')",
            name="ck_company_record_status",
        ),
        sa.UniqueConstraint("standard_name", name="uq_company_standard_name"),
        sa.UniqueConstraint(
            "business_registration_no",
            name="uq_company_business_registration_no",
        ),
    )

    company_table = sa.table(
        "company",
        sa.column("company_id", sa.String()),
        sa.column("standard_name", sa.String()),
        sa.column("legal_name", sa.String()),
        sa.column("business_registration_no", sa.String()),
        sa.column("official_url", sa.Text()),
    )
    op.bulk_insert(
        company_table,
        [
            {
                "company_id": company_id,
                "standard_name": standard_name,
                "legal_name": legal_name,
                "business_registration_no": registration_no,
                "official_url": official_url,
            }
            for company_id, standard_name, legal_name, registration_no, official_url in COMPANIES
        ],
    )

    op.create_table(
        "company_alias",
        sa.Column(
            "alias_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            sa.String(length=30),
            sa.ForeignKey("company.company_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias_raw", sa.String(length=250), nullable=False),
        sa.Column("alias_normalized", sa.String(length=250), nullable=False),
        sa.Column("alias_type", sa.String(length=30), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("official_url", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'CONFIRMED'"),
        ),
        sa.Column(
            "auto_match_allowed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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
            "alias_type IN ('LEGAL', 'BRAND', 'ENGLISH', 'ABBREVIATION', 'LEGACY')",
            name="ck_company_alias_type",
        ),
        sa.CheckConstraint(
            "review_status IN ('CANDIDATE', 'CONFIRMED', 'REVIEW_REQUIRED', 'REJECTED')",
            name="ck_company_alias_review_status",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_company_alias_valid_period",
        ),
        sa.UniqueConstraint(
            "company_id", "alias_raw", name="uq_company_alias_company_raw"
        ),
    )

    alias_table = sa.table(
        "company_alias",
        sa.column("company_id", sa.String()),
        sa.column("alias_raw", sa.String()),
        sa.column("alias_normalized", sa.String()),
        sa.column("alias_type", sa.String()),
    )
    op.bulk_insert(
        alias_table,
        [
            {
                "company_id": company_id,
                "alias_raw": alias_raw,
                "alias_normalized": alias_normalized,
                "alias_type": alias_type,
            }
            for company_id, alias_raw, alias_normalized, alias_type in ALIASES
        ],
    )

    op.create_table(
        "company_role_type",
        sa.Column("role_code", sa.String(length=30), primary_key=True),
        sa.Column("role_name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    role_table = sa.table(
        "company_role_type",
        sa.column("role_code", sa.String()),
        sa.column("role_name", sa.String()),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        role_table,
        [
            {
                "role_code": role_code,
                "role_name": role_name,
                "description": description,
            }
            for role_code, role_name, description in ROLES
        ],
    )

    op.create_table(
        "company_participation",
        sa.Column(
            "participation_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            sa.String(length=30),
            sa.ForeignKey("company.company_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role_code",
            sa.String(length=30),
            sa.ForeignKey("company_role_type.role_code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'CANDIDATE'"),
        ),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("evidence_url", sa.Text(), nullable=True),
        sa.Column("evidence_location", sa.Text(), nullable=True),
        sa.Column(
            "public_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
            "scope_type IN ('SITE', 'PROJECT', 'PHASE')",
            name="ck_company_participation_scope_type",
        ),
        sa.CheckConstraint(
            "review_status IN ('CANDIDATE', 'CONFIRMED', 'CONFLICT', 'REJECTED')",
            name="ck_company_participation_review_status",
        ),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_company_participation_confidence",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_company_participation_valid_period",
        ),
    )

    op.create_table(
        "company_relationship",
        sa.Column(
            "relationship_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "from_company_id",
            sa.String(length=30),
            sa.ForeignKey("company.company_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "to_company_id",
            sa.String(length=30),
            sa.ForeignKey("company.company_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("relationship_type", sa.String(length=30), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'CANDIDATE'"),
        ),
        sa.Column("evidence_url", sa.Text(), nullable=True),
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
            "from_company_id <> to_company_id",
            name="ck_company_relationship_not_self",
        ),
        sa.CheckConstraint(
            "relationship_type IN ('PARENT', 'SUBSIDIARY', 'AFFILIATE', "
            "'INVESTOR', 'SHAREHOLDER', 'SPC_SPONSOR')",
            name="ck_company_relationship_type",
        ),
        sa.CheckConstraint(
            "review_status IN ('CANDIDATE', 'CONFIRMED', 'CONFLICT', 'REJECTED')",
            name="ck_company_relationship_review_status",
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_company_relationship_valid_period",
        ),
    )

    op.create_index(
        "idx_company_alias_normalized",
        "company_alias",
        ["alias_normalized"],
        unique=False,
    )
    op.create_index(
        "idx_company_participation_scope",
        "company_participation",
        ["scope_type", "scope_id"],
        unique=False,
    )
    op.create_index(
        "idx_company_participation_company_role",
        "company_participation",
        ["company_id", "role_code"],
        unique=False,
    )
    op.create_index(
        "idx_company_relationship_from",
        "company_relationship",
        ["from_company_id"],
        unique=False,
    )
    op.create_index(
        "idx_company_relationship_to",
        "company_relationship",
        ["to_company_id"],
        unique=False,
    )

    for table_name in (
        "company",
        "company_alias",
        "company_participation",
        "company_relationship",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )


def downgrade() -> None:
    op.drop_index("idx_company_relationship_to", table_name="company_relationship")
    op.drop_index("idx_company_relationship_from", table_name="company_relationship")
    op.drop_table("company_relationship")

    op.drop_index(
        "idx_company_participation_company_role",
        table_name="company_participation",
    )
    op.drop_index(
        "idx_company_participation_scope",
        table_name="company_participation",
    )
    op.drop_table("company_participation")
    op.drop_table("company_role_type")

    op.drop_index("idx_company_alias_normalized", table_name="company_alias")
    op.drop_table("company_alias")
    op.drop_table("company")
