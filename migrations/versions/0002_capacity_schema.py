"""Create capacity types and time-based capacity snapshots.

Revision ID: 0002_capacity_schema
Revises: 0001_core_schema
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0002_capacity_schema"
down_revision: Union[str, None] = "0001_core_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CAPACITY_TYPES = (
    (
        "GRID_INTAKE_MW",
        "수전용량",
        "MW",
        True,
        "외부 전력계통에서 인입 가능한 유효전력 규모",
    ),
    (
        "CONTRACT_POWER_MW",
        "계약전력",
        "MW",
        True,
        "전력공급자와 수용장소 기준으로 계약된 전력",
    ),
    (
        "IT_LOAD_MW",
        "IT Load",
        "MW",
        True,
        "서버·스토리지·네트워크·GPU 등 IT 장비 공급 전력",
    ),
    (
        "GPU_POWER_MW",
        "GPU 전력",
        "MW",
        True,
        "GPU 장비 또는 GPU 서버에 배정·계약·측정된 IT 전력",
    ),
    (
        "ANNOUNCED_UNCLASSIFIED_MW",
        "발표용량(유형 미확정)",
        "MW",
        False,
        "전력 유형과 경계가 확인되지 않은 대외 발표값",
    ),
    (
        "APPARENT_POWER_MVA",
        "피상전력",
        "MVA",
        False,
        "역률 적용 전 피상전력",
    ),
    (
        "UPS_RATING_KW",
        "UPS 정격",
        "kW",
        False,
        "무정전전원장치 정격 용량",
    ),
    (
        "RACK_POWER_KW",
        "랙 전력",
        "kW",
        False,
        "랙 단위 설계·배정·측정 전력",
    ),
    (
        "TENANT_COMMITTED_IT_MW",
        "임차고객 계약 IT 전력",
        "MW",
        False,
        "고객 상면 계약에 약정된 IT 전력",
    ),
    (
        "RENEWABLE_SUPPLY_MW",
        "재생에너지 조달 규모",
        "MW",
        False,
        "재생에너지 공급 또는 조달 규모",
    ),
    (
        "ENERGY_MWH",
        "에너지 사용량",
        "MWh",
        False,
        "특정 기간에 사용한 전력 에너지",
    ),
    (
        "PUE",
        "PUE",
        "RATIO",
        False,
        "동일 기간·경계의 전체 시설 에너지 대비 IT 에너지 비율",
    ),
)


def upgrade() -> None:
    op.create_table(
        "capacity_type",
        sa.Column("capacity_type_code", sa.String(length=40), primary_key=True),
        sa.Column("capacity_type_name", sa.String(length=100), nullable=False),
        sa.Column("standard_unit", sa.String(length=20), nullable=False),
        sa.Column(
            "default_aggregation_eligible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "active",
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
    )

    capacity_type_table = sa.table(
        "capacity_type",
        sa.column("capacity_type_code", sa.String()),
        sa.column("capacity_type_name", sa.String()),
        sa.column("standard_unit", sa.String()),
        sa.column("default_aggregation_eligible", sa.Boolean()),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        capacity_type_table,
        [
            {
                "capacity_type_code": code,
                "capacity_type_name": name,
                "standard_unit": unit,
                "default_aggregation_eligible": eligible,
                "description": description,
            }
            for code, name, unit, eligible, description in CAPACITY_TYPES
        ],
    )

    op.create_table(
        "capacity_snapshot",
        sa.Column(
            "capacity_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("scope_type", sa.String(length=20), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "capacity_type_code",
            sa.String(length=40),
            sa.ForeignKey(
                "capacity_type.capacity_type_code",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("raw_unit", sa.String(length=30), nullable=False),
        sa.Column("raw_phrase", sa.Text(), nullable=True),
        sa.Column("normalized_value_mw", sa.Numeric(precision=16, scale=3), nullable=True),
        sa.Column("normalized_value", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("normalized_unit", sa.String(length=20), nullable=True),
        sa.Column("capacity_stage", sa.String(length=30), nullable=False),
        sa.Column("measurement_basis", sa.String(length=30), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("document_url", sa.Text(), nullable=True),
        sa.Column("evidence_location", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'CANDIDATE'"),
        ),
        sa.Column(
            "overlaps_capacity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("capacity_snapshot.capacity_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "aggregation_excluded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
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
            "scope_type IN ('SITE', 'PROJECT', 'PHASE', 'BUILDING', 'MODULE', 'RACK')",
            name="ck_capacity_snapshot_scope_type",
        ),
        sa.CheckConstraint(
            "capacity_stage IN ('ANNOUNCED', 'SECURED', 'DESIGNED', "
            "'UNDER_CONSTRUCTION', 'INSTALLED', 'OPERATING')",
            name="ck_capacity_snapshot_stage",
        ),
        sa.CheckConstraint(
            "measurement_basis IN ('PUBLISHED_CAPACITY', 'NAMEPLATE', "
            "'CONTRACTED', 'AVAILABLE', 'ALLOCATED', 'METERED_PEAK', "
            "'METERED_AVG')",
            name="ck_capacity_snapshot_basis",
        ),
        sa.CheckConstraint(
            "review_status IN ('CANDIDATE', 'CONFIRMED', 'CONFLICT', 'REJECTED')",
            name="ck_capacity_snapshot_review_status",
        ),
        sa.CheckConstraint(
            "normalized_value_mw IS NULL OR normalized_value_mw > 0",
            name="ck_capacity_snapshot_positive_mw",
        ),
        sa.CheckConstraint(
            "normalized_value IS NULL OR normalized_value > 0",
            name="ck_capacity_snapshot_positive_value",
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_capacity_snapshot_effective_period",
        ),
        sa.CheckConstraint(
            "aggregation_excluded = false OR exclusion_reason IS NOT NULL",
            name="ck_capacity_snapshot_exclusion_reason",
        ),
    )

    op.create_index(
        "idx_capacity_snapshot_scope",
        "capacity_snapshot",
        ["scope_type", "scope_id"],
        unique=False,
    )
    op.create_index(
        "idx_capacity_snapshot_type",
        "capacity_snapshot",
        ["capacity_type_code"],
        unique=False,
    )
    op.create_index(
        "idx_capacity_snapshot_effective",
        "capacity_snapshot",
        ["effective_from", "effective_to"],
        unique=False,
    )
    op.create_index(
        "idx_capacity_snapshot_review",
        "capacity_snapshot",
        ["review_status", "capacity_stage"],
        unique=False,
    )

    op.execute(
        """
        CREATE TRIGGER trg_capacity_type_updated_at
        BEFORE UPDATE ON capacity_type
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_capacity_snapshot_updated_at
        BEFORE UPDATE ON capacity_snapshot
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_capacity_snapshot_updated_at ON capacity_snapshot"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_capacity_type_updated_at ON capacity_type")

    op.drop_index("idx_capacity_snapshot_review", table_name="capacity_snapshot")
    op.drop_index("idx_capacity_snapshot_effective", table_name="capacity_snapshot")
    op.drop_index("idx_capacity_snapshot_type", table_name="capacity_snapshot")
    op.drop_index("idx_capacity_snapshot_scope", table_name="capacity_snapshot")
    op.drop_table("capacity_snapshot")
    op.drop_table("capacity_type")
