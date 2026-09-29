"""Create events, change requests, field changes, and review actions.

Revision ID: 0005_event_review
Revises: 0004_evidence_fact
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0005_event_review"
down_revision: Union[str, None] = "0004_evidence_fact"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dc_event",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scope_type", sa.String(length=30), nullable=False),
        sa.Column("scope_id", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("date_precision", sa.String(length=20), nullable=False),
        sa.Column("event_date_raw", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "source_fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extracted_fact.fact_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'CANDIDATE'"),
        ),
        sa.Column(
            "public_visible",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "scope_type IN ('SITE', 'PROJECT', 'PHASE', 'COMPANY')",
            name="ck_dc_event_scope_type",
        ),
        sa.CheckConstraint(
            "event_type IN ('ANNOUNCEMENT', 'SITE_ACQUIRED', 'PERMIT', "
            "'POWER_SECURED', 'CONSTRUCTION_START', 'COMPLETION', 'RFS', "
            "'SERVICE_START', 'STATUS_CHANGE', 'CAPACITY_CHANGE', "
            "'OWNERSHIP_CHANGE', 'CANCELLATION', 'OTHER')",
            name="ck_dc_event_type",
        ),
        sa.CheckConstraint(
            "date_precision IN ('DAY', 'MONTH', 'QUARTER', 'HALF_YEAR', 'YEAR', 'UNKNOWN')",
            name="ck_dc_event_date_precision",
        ),
        sa.CheckConstraint(
            "review_status IN ('CANDIDATE', 'CONFIRMED', 'CONFLICT', 'REJECTED')",
            name="ck_dc_event_review_status",
        ),
    )

    op.create_table(
        "change_request",
        sa.Column(
            "change_request_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scope_type", sa.String(length=30), nullable=False),
        sa.Column("scope_id", sa.String(length=100), nullable=False),
        sa.Column("change_type", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "source_fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extracted_fact.fact_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requested_by", sa.String(length=150), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("assigned_to", sa.String(length=150), nullable=True),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default=sa.text("'NORMAL'")),
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("reviewed_by", sa.String(length=150), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
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
            "scope_type IN ('SITE', 'PROJECT', 'PHASE', 'COMPANY', 'CAPACITY', 'FACT', 'EVENT')",
            name="ck_change_request_scope_type",
        ),
        sa.CheckConstraint(
            "change_type IN ('CREATE', 'UPDATE', 'MERGE', 'DELETE', 'RESTORE')",
            name="ck_change_request_type",
        ),
        sa.CheckConstraint(
            "priority IN ('LOW', 'NORMAL', 'HIGH', 'URGENT')",
            name="ck_change_request_priority",
        ),
        sa.CheckConstraint(
            "review_status IN ('PENDING', 'IN_REVIEW', 'APPROVED', 'REJECTED', "
            "'CHANGES_REQUESTED', 'CANCELLED', 'APPLIED')",
            name="ck_change_request_review_status",
        ),
        sa.CheckConstraint(
            "review_status NOT IN ('APPROVED', 'REJECTED', 'APPLIED') "
            "OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL AND decision_reason IS NOT NULL)",
            name="ck_change_request_final_decision",
        ),
        sa.CheckConstraint(
            "review_status NOT IN ('APPROVED', 'APPLIED') OR reviewed_by <> requested_by",
            name="ck_change_request_no_self_approval",
        ),
    )

    op.create_table(
        "field_change",
        sa.Column(
            "field_change_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "change_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("change_request.change_request_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("change_operation", sa.String(length=20), nullable=False),
        sa.Column("before_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "sensitive",
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
        sa.CheckConstraint(
            "entity_type IN ('SITE', 'PROJECT', 'PHASE', 'COMPANY', 'CAPACITY', 'FACT', 'EVENT')",
            name="ck_field_change_entity_type",
        ),
        sa.CheckConstraint(
            "change_operation IN ('ADD', 'MODIFY', 'REMOVE')",
            name="ck_field_change_operation",
        ),
        sa.CheckConstraint(
            "before_value IS NOT NULL OR after_value IS NOT NULL",
            name="ck_field_change_has_value",
        ),
    )

    op.create_table(
        "review_action",
        sa.Column(
            "review_action_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "change_request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("change_request.change_request_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(length=150), nullable=False),
        sa.Column("role_at_action", sa.String(length=30), nullable=False),
        sa.Column("action_type", sa.String(length=30), nullable=False),
        sa.Column("action_reason", sa.Text(), nullable=True),
        sa.Column("action_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "role_at_action IN ('VIEWER', 'ANALYST', 'REVIEWER', 'ADMIN', 'SYSTEM')",
            name="ck_review_action_role",
        ),
        sa.CheckConstraint(
            "action_type IN ('SUBMIT', 'ASSIGN', 'START_REVIEW', 'APPROVE', "
            "'REJECT', 'REQUEST_CHANGES', 'MERGE', 'CANCEL', 'APPLY', 'COMMENT')",
            name="ck_review_action_type",
        ),
    )

    op.create_index(
        "idx_dc_event_scope_date",
        "dc_event",
        ["scope_type", "scope_id", "event_date"],
        unique=False,
    )
    op.create_index(
        "idx_dc_event_type_status",
        "dc_event",
        ["event_type", "review_status"],
        unique=False,
    )
    op.create_index(
        "idx_change_request_queue",
        "change_request",
        ["review_status", "priority", "requested_at"],
        unique=False,
    )
    op.create_index(
        "idx_change_request_scope",
        "change_request",
        ["scope_type", "scope_id"],
        unique=False,
    )
    op.create_index(
        "idx_field_change_request",
        "field_change",
        ["change_request_id", "entity_type", "entity_id"],
        unique=False,
    )
    op.create_index(
        "idx_review_action_request_time",
        "review_action",
        ["change_request_id", "created_at"],
        unique=False,
    )

    for table_name in ("dc_event", "change_request"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )


def downgrade() -> None:
    op.drop_index(
        "idx_review_action_request_time",
        table_name="review_action",
    )
    op.drop_table("review_action")

    op.drop_index("idx_field_change_request", table_name="field_change")
    op.drop_table("field_change")

    op.drop_index("idx_change_request_scope", table_name="change_request")
    op.drop_index("idx_change_request_queue", table_name="change_request")
    op.drop_table("change_request")

    op.drop_index("idx_dc_event_type_status", table_name="dc_event")
    op.drop_index("idx_dc_event_scope_date", table_name="dc_event")
    op.drop_table("dc_event")
