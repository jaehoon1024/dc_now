"""Create evidence documents, document versions, and extracted facts.

Revision ID: 0004_evidence_fact
Revises: 0003_company_participation
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0004_evidence_fact"
down_revision: Union[str, None] = "0003_company_participation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_registry",
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("source_code", sa.String(length=50), nullable=False),
        sa.Column("source_name", sa.String(length=250), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("default_source_grade", sa.CHAR(length=1), nullable=False),
        sa.Column("collection_method", sa.String(length=20), nullable=False),
        sa.Column("collection_interval", sa.String(length=30), nullable=True),
        sa.Column(
            "terms_review_status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("owner_name", sa.String(length=100), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
            "source_type IN ('GOVERNMENT', 'REGULATOR', 'COMPANY', "
            "'INDUSTRY', 'NEWS', 'BLOG', 'OTHER')",
            name="ck_source_registry_type",
        ),
        sa.CheckConstraint(
            "default_source_grade IN ('A', 'B', 'C', 'D')",
            name="ck_source_registry_grade",
        ),
        sa.CheckConstraint(
            "collection_method IN ('API', 'RSS', 'HTML', 'PDF', 'FILE', 'MANUAL')",
            name="ck_source_registry_method",
        ),
        sa.CheckConstraint(
            "terms_review_status IN ('PENDING', 'ALLOWED', 'LIMITED', 'PROHIBITED')",
            name="ck_source_registry_terms_status",
        ),
        sa.UniqueConstraint("source_code", name="uq_source_registry_code"),
    )

    op.create_table(
        "evidence_document",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("external_document_id", sa.String(length=250), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("document_type", sa.String(length=30), nullable=False),
        sa.Column("publisher", sa.String(length=250), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language_code", sa.String(length=10), nullable=False, server_default=sa.text("'ko'")),
        sa.Column("source_grade", sa.CHAR(length=1), nullable=False),
        sa.Column(
            "access_scope",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'PUBLIC'"),
        ),
        sa.Column(
            "record_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
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
            "document_type IN ('PERMIT', 'CONTRACT', 'DISCLOSURE', 'PRESS_RELEASE', "
            "'NEWS', 'IM', 'WEB_PAGE', 'PDF', 'API_RESPONSE', 'RSS_ITEM', 'OTHER')",
            name="ck_evidence_document_type",
        ),
        sa.CheckConstraint(
            "source_grade IN ('A', 'B', 'C', 'D')",
            name="ck_evidence_document_grade",
        ),
        sa.CheckConstraint(
            "access_scope IN ('PUBLIC', 'INTERNAL', 'CONFIDENTIAL')",
            name="ck_evidence_document_access_scope",
        ),
        sa.CheckConstraint(
            "record_status IN ('ACTIVE', 'INACTIVE', 'DELETED_AT_SOURCE')",
            name="ck_evidence_document_record_status",
        ),
    )

    op.create_table(
        "evidence_document_version",
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_document.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=150), nullable=True),
        sa.Column("content_hash_sha256", sa.CHAR(length=64), nullable=False),
        sa.Column("raw_storage_path", sa.Text(), nullable=False),
        sa.Column("extracted_text_path", sa.Text(), nullable=True),
        sa.Column("parser_name", sa.String(length=100), nullable=True),
        sa.Column("parser_version", sa.String(length=50), nullable=True),
        sa.Column("extraction_status", sa.String(length=20), nullable=False, server_default=sa.text("'PENDING'")),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "version_no >= 1",
            name="ck_evidence_document_version_no",
        ),
        sa.CheckConstraint(
            "http_status IS NULL OR (http_status >= 100 AND http_status <= 599)",
            name="ck_evidence_document_http_status",
        ),
        sa.CheckConstraint(
            "extraction_status IN ('PENDING', 'SUCCESS', 'PARTIAL', 'FAILED')",
            name="ck_evidence_document_extraction_status",
        ),
        sa.UniqueConstraint(
            "document_id", "version_no", name="uq_evidence_document_version_no"
        ),
        sa.UniqueConstraint(
            "document_id",
            "content_hash_sha256",
            name="uq_evidence_document_content_hash",
        ),
    )

    op.create_table(
        "extracted_fact",
        sa.Column(
            "fact_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scope_type", sa.String(length=30), nullable=False),
        sa.Column("scope_id", sa.String(length=100), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("value_type", sa.String(length=20), nullable=False),
        sa.Column("raw_value_text", sa.Text(), nullable=False),
        sa.Column("normalized_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("normalized_unit", sa.String(length=30), nullable=True),
        sa.Column("claim_origin", sa.String(length=20), nullable=False),
        sa.Column("source_grade", sa.CHAR(length=1), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'CANDIDATE'"),
        ),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("conflict_group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=150), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
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
            "scope_type IN ('SITE', 'PROJECT', 'PHASE', 'COMPANY', 'CAPACITY', 'EVENT')",
            name="ck_extracted_fact_scope_type",
        ),
        sa.CheckConstraint(
            "value_type IN ('TEXT', 'NUMBER', 'DATE', 'BOOLEAN', 'JSON')",
            name="ck_extracted_fact_value_type",
        ),
        sa.CheckConstraint(
            "claim_origin IN ('PRIMARY', 'REQUOTE', 'INFERENCE')",
            name="ck_extracted_fact_claim_origin",
        ),
        sa.CheckConstraint(
            "source_grade IN ('A', 'B', 'C', 'D')",
            name="ck_extracted_fact_source_grade",
        ),
        sa.CheckConstraint(
            "review_status IN ('CANDIDATE', 'CONFIRMED', 'CONFLICT', 'REJECTED')",
            name="ck_extracted_fact_review_status",
        ),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name="ck_extracted_fact_confidence",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_extracted_fact_effective_period",
        ),
        sa.CheckConstraint(
            "review_status <> 'REJECTED' OR rejection_reason IS NOT NULL",
            name="ck_extracted_fact_rejection_reason",
        ),
    )

    op.create_table(
        "fact_evidence",
        sa.Column(
            "fact_evidence_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extracted_fact.fact_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "evidence_document_version.document_version_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("evidence_locator", sa.Text(), nullable=False),
        sa.Column("quote_text", sa.Text(), nullable=True),
        sa.Column(
            "is_primary_evidence",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "fact_id",
            "document_version_id",
            "evidence_locator",
            name="uq_fact_evidence_location",
        ),
    )

    op.create_index(
        "idx_evidence_document_source",
        "evidence_document",
        ["source_id", "published_at"],
        unique=False,
    )
    op.create_index(
        "idx_evidence_document_url",
        "evidence_document",
        ["canonical_url"],
        unique=False,
    )
    op.create_index(
        "idx_evidence_document_version_current",
        "evidence_document_version",
        ["document_id", "is_current"],
        unique=False,
    )
    op.create_index(
        "idx_extracted_fact_scope_field",
        "extracted_fact",
        ["scope_type", "scope_id", "field_name"],
        unique=False,
    )
    op.create_index(
        "idx_extracted_fact_review",
        "extracted_fact",
        ["review_status", "source_grade"],
        unique=False,
    )
    op.create_index(
        "idx_extracted_fact_conflict",
        "extracted_fact",
        ["conflict_group_id"],
        unique=False,
    )
    op.create_index(
        "idx_fact_evidence_document_version",
        "fact_evidence",
        ["document_version_id"],
        unique=False,
    )

    for table_name in (
        "source_registry",
        "evidence_document",
        "extracted_fact",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )


def downgrade() -> None:
    op.drop_index(
        "idx_fact_evidence_document_version",
        table_name="fact_evidence",
    )
    op.drop_table("fact_evidence")

    op.drop_index("idx_extracted_fact_conflict", table_name="extracted_fact")
    op.drop_index("idx_extracted_fact_review", table_name="extracted_fact")
    op.drop_index("idx_extracted_fact_scope_field", table_name="extracted_fact")
    op.drop_table("extracted_fact")

    op.drop_index(
        "idx_evidence_document_version_current",
        table_name="evidence_document_version",
    )
    op.drop_table("evidence_document_version")

    op.drop_index("idx_evidence_document_url", table_name="evidence_document")
    op.drop_index("idx_evidence_document_source", table_name="evidence_document")
    op.drop_table("evidence_document")
    op.drop_table("source_registry")
