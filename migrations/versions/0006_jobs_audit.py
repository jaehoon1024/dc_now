"""Create collection runs, export jobs, and audit logs.

Revision ID: 0006_jobs_audit
Revises: 0005_event_review
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0006_jobs_audit"
down_revision: Union[str, None] = "0005_event_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collection_run",
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("job_name", sa.String(length=150), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column("requested_by", sa.String(length=150), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "run_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'QUEUED'"),
        ),
        sa.Column("total_source_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("success_source_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_source_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("new_document_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_document_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("host_name", sa.String(length=200), nullable=True),
        sa.Column("application_version", sa.String(length=100), nullable=True),
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
            "trigger_type IN ('SCHEDULED', 'MANUAL', 'RETRY', 'BACKFILL')",
            name="ck_collection_run_trigger_type",
        ),
        sa.CheckConstraint(
            "run_status IN ('QUEUED', 'RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED', 'CANCELLED')",
            name="ck_collection_run_status",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_collection_run_time_order",
        ),
        sa.CheckConstraint(
            "total_source_count >= 0 AND success_source_count >= 0 AND "
            "failed_source_count >= 0 AND new_document_count >= 0 AND "
            "updated_document_count >= 0",
            name="ck_collection_run_nonnegative_counts",
        ),
    )

    op.create_table(
        "collection_source_run",
        sa.Column(
            "collection_source_run_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "collection_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("collection_run.collection_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("source_registry.source_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "run_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'QUEUED'"),
        ),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("found_item_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("new_item_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_item_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped_item_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("downloaded_bytes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_log_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("attempt_no >= 1", name="ck_collection_source_run_attempt"),
        sa.CheckConstraint(
            "run_status IN ('QUEUED', 'RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED', 'RETRY_WAIT')",
            name="ck_collection_source_run_status",
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_collection_source_run_time_order",
        ),
        sa.CheckConstraint(
            "request_count >= 0 AND found_item_count >= 0 AND new_item_count >= 0 "
            "AND updated_item_count >= 0 AND skipped_item_count >= 0 AND downloaded_bytes >= 0",
            name="ck_collection_source_run_nonnegative_counts",
        ),
        sa.UniqueConstraint(
            "collection_run_id",
            "source_id",
            "attempt_no",
            name="uq_collection_source_run_attempt",
        ),
    )

    op.create_table(
        "export_job",
        sa.Column(
            "export_job_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("requested_by", sa.String(length=150), nullable=False),
        sa.Column("requested_role", sa.String(length=30), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("export_format", sa.String(length=20), nullable=False),
        sa.Column("access_scope", sa.String(length=20), nullable=False),
        sa.Column("filters_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("columns_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("row_count", sa.BigInteger(), nullable=True),
        sa.Column(
            "job_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'QUEUED'"),
        ),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column("file_hash_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("approved_by", sa.String(length=150), nullable=True),
        sa.Column("approval_reason", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("download_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            "requested_role IN ('VIEWER', 'ANALYST', 'REVIEWER', 'ADMIN')",
            name="ck_export_job_requested_role",
        ),
        sa.CheckConstraint(
            "export_format IN ('CSV', 'XLSX', 'PDF', 'GEOJSON')",
            name="ck_export_job_format",
        ),
        sa.CheckConstraint(
            "access_scope IN ('PUBLIC', 'INTERNAL', 'CONFIDENTIAL')",
            name="ck_export_job_access_scope",
        ),
        sa.CheckConstraint(
            "job_status IN ('QUEUED', 'RUNNING', 'SUCCESS', 'FAILED', 'EXPIRED', 'DELETED', 'CANCELLED')",
            name="ck_export_job_status",
        ),
        sa.CheckConstraint(
            "row_count IS NULL OR row_count >= 0",
            name="ck_export_job_row_count",
        ),
        sa.CheckConstraint(
            "access_scope <> 'CONFIDENTIAL' OR approved_by IS NOT NULL",
            name="ck_export_job_confidential_approval",
        ),
        sa.CheckConstraint(
            "download_expires_at IS NULL OR completed_at IS NULL OR download_expires_at >= completed_at",
            name="ck_export_job_expiry_order",
        ),
        sa.CheckConstraint(
            "delete_after IS NULL OR download_expires_at IS NULL OR delete_after >= download_expires_at",
            name="ck_export_job_delete_order",
        ),
    )

    op.create_table(
        "audit_log",
        sa.Column(
            "audit_log_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("actor_id", sa.String(length=150), nullable=False),
        sa.Column("role_at_action", sa.String(length=30), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.String(length=150), nullable=True),
        sa.Column("request_id", sa.String(length=150), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("before_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.String(length=150), nullable=True),
        sa.Column(
            "export_job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("export_job.export_job_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("export_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("export_row_count", sa.BigInteger(), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "role_at_action IN ('VIEWER', 'ANALYST', 'REVIEWER', 'ADMIN', 'SYSTEM')",
            name="ck_audit_log_role",
        ),
        sa.CheckConstraint(
            "result IN ('SUCCESS', 'DENIED', 'FAILED')",
            name="ck_audit_log_result",
        ),
        sa.CheckConstraint(
            "export_row_count IS NULL OR export_row_count >= 0",
            name="ck_audit_log_export_row_count",
        ),
    )

    op.create_index(
        "idx_collection_run_status_time",
        "collection_run",
        ["run_status", "scheduled_at"],
        unique=False,
    )
    op.create_index(
        "idx_collection_source_run_source_time",
        "collection_source_run",
        ["source_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_export_job_user_time",
        "export_job",
        ["requested_by", "requested_at"],
        unique=False,
    )
    op.create_index(
        "idx_export_job_status_expiry",
        "export_job",
        ["job_status", "download_expires_at", "delete_after"],
        unique=False,
    )
    op.create_index(
        "idx_audit_log_actor_time",
        "audit_log",
        ["actor_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "idx_audit_log_entity_time",
        "audit_log",
        ["entity_type", "entity_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "idx_audit_log_action_result",
        "audit_log",
        ["action", "result", "occurred_at"],
        unique=False,
    )

    for table_name in ("collection_run", "export_job"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_updated_at
            BEFORE UPDATE ON {table_name}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )


def downgrade() -> None:
    op.drop_index("idx_audit_log_action_result", table_name="audit_log")
    op.drop_index("idx_audit_log_entity_time", table_name="audit_log")
    op.drop_index("idx_audit_log_actor_time", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("idx_export_job_status_expiry", table_name="export_job")
    op.drop_index("idx_export_job_user_time", table_name="export_job")
    op.drop_table("export_job")

    op.drop_index(
        "idx_collection_source_run_source_time",
        table_name="collection_source_run",
    )
    op.drop_table("collection_source_run")

    op.drop_index("idx_collection_run_status_time", table_name="collection_run")
    op.drop_table("collection_run")
