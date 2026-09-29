"""Create the core data-center hierarchy.

Revision ID: 0001_core_schema
Revises: None
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql


revision: str = "0001_core_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATUS_CHECK = """
status_code IS NULL OR status_code IN (
    'IDEA',
    'SITE_SECURED',
    'PERMITTING',
    'POWER_SECURED',
    'CONSTRUCTION',
    'READY',
    'OPERATING',
    'ON_HOLD',
    'CANCELLED'
)
"""


def upgrade() -> None:
    # PostGIS는 DB 관리자가 미리 활성화해야 합니다. 이미 존재하면 안전하게 통과합니다.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "dc_site",
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("site_code", sa.String(length=30), nullable=False),
        sa.Column("site_name", sa.String(length=200), nullable=False),
        sa.Column("site_name_raw", sa.String(length=200), nullable=True),
        sa.Column("address_raw", sa.Text(), nullable=False),
        sa.Column("address_standard", sa.Text(), nullable=True),
        sa.Column("sido", sa.String(length=50), nullable=True),
        sa.Column("sigungu", sa.String(length=50), nullable=True),
        sa.Column(
            "location_precision",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'UNKNOWN'"),
        ),
        sa.Column(
            "coordinate_quality",
            sa.CHAR(length=1),
            nullable=False,
            server_default=sa.text("'U'"),
        ),
        sa.Column(
            "geom",
            Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column(
            "review_status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'NEEDS_EVIDENCE'"),
        ),
        sa.Column(
            "record_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "coordinate_quality IN ('A', 'B', 'C', 'D', 'U')",
            name="ck_dc_site_coordinate_quality",
        ),
        sa.CheckConstraint(
            "record_status IN ('ACTIVE', 'INACTIVE')",
            name="ck_dc_site_record_status",
        ),
        sa.UniqueConstraint("site_code", name="uq_dc_site_site_code"),
    )

    op.create_index(
        "idx_dc_site_geom",
        "dc_site",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "dc_project",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_code", sa.String(length=30), nullable=False),
        sa.Column(
            "site_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dc_site.site_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("project_name", sa.String(length=200), nullable=False),
        sa.Column("project_type", sa.String(length=30), nullable=True),
        sa.Column("project_scope", sa.Text(), nullable=False),
        sa.Column("status_code", sa.String(length=30), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'NEEDS_EVIDENCE'"),
        ),
        sa.Column("scope_note", sa.Text(), nullable=True),
        sa.Column("planned_rfs_date", sa.Date(), nullable=True),
        sa.Column("rfs_date", sa.Date(), nullable=True),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("service_start_date", sa.Date(), nullable=True),
        sa.Column(
            "public_visible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(STATUS_CHECK, name="ck_dc_project_status_code"),
        sa.CheckConstraint(
            "record_status IN ('ACTIVE', 'INACTIVE')",
            name="ck_dc_project_record_status",
        ),
        sa.UniqueConstraint("project_code", name="uq_dc_project_project_code"),
    )

    op.create_index(
        "idx_dc_project_site_id", "dc_project", ["site_id"], unique=False
    )
    op.create_index(
        "idx_dc_project_status_code", "dc_project", ["status_code"], unique=False
    )

    op.create_table(
        "project_phase",
        sa.Column(
            "phase_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("phase_code", sa.String(length=30), nullable=False),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dc_project.project_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("phase_name", sa.String(length=200), nullable=False),
        sa.Column("phase_order", sa.Integer(), nullable=True),
        sa.Column("scope_description", sa.Text(), nullable=False),
        sa.Column("status_code", sa.String(length=30), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'NEEDS_EVIDENCE'"),
        ),
        sa.Column("construction_start_date", sa.Date(), nullable=True),
        sa.Column("planned_rfs_date", sa.Date(), nullable=True),
        sa.Column("rfs_date", sa.Date(), nullable=True),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("service_start_date", sa.Date(), nullable=True),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "phase_order IS NULL OR phase_order >= 1",
            name="ck_project_phase_order",
        ),
        sa.CheckConstraint(STATUS_CHECK, name="ck_project_phase_status_code"),
        sa.CheckConstraint(
            "record_status IN ('ACTIVE', 'INACTIVE')",
            name="ck_project_phase_record_status",
        ),
        sa.UniqueConstraint("phase_code", name="uq_project_phase_phase_code"),
    )

    op.create_index(
        "idx_project_phase_project_id",
        "project_phase",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "idx_project_phase_status_code",
        "project_phase",
        ["status_code"],
        unique=False,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_dc_site_updated_at
        BEFORE UPDATE ON dc_site
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_dc_project_updated_at
        BEFORE UPDATE ON dc_project
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_project_phase_updated_at
        BEFORE UPDATE ON project_phase
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.drop_index("idx_project_phase_status_code", table_name="project_phase")
    op.drop_index("idx_project_phase_project_id", table_name="project_phase")
    op.drop_table("project_phase")

    op.drop_index("idx_dc_project_status_code", table_name="dc_project")
    op.drop_index("idx_dc_project_site_id", table_name="dc_project")
    op.drop_table("dc_project")

    op.drop_index("idx_dc_site_geom", table_name="dc_site")
    op.drop_table("dc_site")

    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
