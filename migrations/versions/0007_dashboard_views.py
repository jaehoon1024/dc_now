"""Create dashboard views for maps, companies, years, and collection health.

Revision ID: 0007_dashboard_views
Revises: 0006_jobs_audit
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0007_dashboard_views"
down_revision: Union[str, None] = "0006_jobs_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIEW v_capacity_current AS
        SELECT DISTINCT ON (
            cs.scope_type,
            cs.scope_id,
            cs.capacity_type_code,
            cs.capacity_stage,
            cs.measurement_basis
        )
            cs.capacity_id,
            cs.scope_type,
            cs.scope_id,
            cs.capacity_type_code,
            ct.capacity_type_name,
            cs.normalized_value_mw,
            cs.normalized_value,
            cs.normalized_unit,
            cs.capacity_stage,
            cs.measurement_basis,
            cs.effective_from,
            cs.effective_to,
            cs.published_at,
            cs.document_url,
            cs.evidence_location,
            cs.review_status,
            cs.created_at,
            cs.updated_at
        FROM capacity_snapshot cs
        JOIN capacity_type ct
          ON ct.capacity_type_code = cs.capacity_type_code
        WHERE cs.review_status = 'CONFIRMED'
          AND cs.aggregation_excluded = false
          AND (cs.effective_from IS NULL OR cs.effective_from <= CURRENT_DATE)
          AND (cs.effective_to IS NULL OR cs.effective_to >= CURRENT_DATE)
        ORDER BY
            cs.scope_type,
            cs.scope_id,
            cs.capacity_type_code,
            cs.capacity_stage,
            cs.measurement_basis,
            cs.effective_from DESC NULLS LAST,
            cs.published_at DESC NULLS LAST,
            cs.updated_at DESC
        """
    )

    op.execute(
        """
        CREATE VIEW v_site_map AS
        WITH project_counts AS (
            SELECT
                p.site_id,
                COUNT(*) FILTER (
                    WHERE p.record_status = 'ACTIVE'
                ) AS total_project_count,
                COUNT(*) FILTER (
                    WHERE p.record_status = 'ACTIVE'
                      AND p.status_code = 'OPERATING'
                ) AS operating_project_count,
                COUNT(*) FILTER (
                    WHERE p.record_status = 'ACTIVE'
                      AND p.status_code IN (
                          'IDEA', 'SITE_SECURED', 'PERMITTING', 'POWER_SECURED',
                          'CONSTRUCTION', 'READY'
                      )
                ) AS development_project_count,
                COUNT(*) FILTER (
                    WHERE p.record_status = 'ACTIVE'
                      AND p.status_code = 'ON_HOLD'
                ) AS on_hold_project_count,
                MIN(COALESCE(p.rfs_date, p.planned_rfs_date)) FILTER (
                    WHERE p.record_status = 'ACTIVE'
                      AND p.status_code <> 'CANCELLED'
                ) AS earliest_rfs_date,
                MAX(p.updated_at) AS latest_project_update
            FROM dc_project p
            GROUP BY p.site_id
        ),
        site_capacity AS (
            SELECT
                vc.scope_id::uuid AS site_id,
                MAX(vc.normalized_value_mw) FILTER (
                    WHERE vc.capacity_type_code = 'GRID_INTAKE_MW'
                      AND vc.capacity_stage = 'OPERATING'
                ) AS operating_grid_intake_mw,
                MAX(vc.normalized_value_mw) FILTER (
                    WHERE vc.capacity_type_code = 'IT_LOAD_MW'
                      AND vc.capacity_stage = 'OPERATING'
                ) AS operating_it_load_mw,
                MAX(vc.normalized_value_mw) FILTER (
                    WHERE vc.capacity_type_code = 'GRID_INTAKE_MW'
                      AND vc.capacity_stage IN (
                          'ANNOUNCED', 'SECURED', 'DESIGNED',
                          'UNDER_CONSTRUCTION', 'INSTALLED'
                      )
                ) AS development_grid_intake_mw,
                MAX(vc.normalized_value_mw) FILTER (
                    WHERE vc.capacity_type_code = 'IT_LOAD_MW'
                      AND vc.capacity_stage IN (
                          'ANNOUNCED', 'SECURED', 'DESIGNED',
                          'UNDER_CONSTRUCTION', 'INSTALLED'
                      )
                ) AS development_it_load_mw,
                MAX(vc.updated_at) AS latest_capacity_update
            FROM v_capacity_current vc
            WHERE vc.scope_type = 'SITE'
            GROUP BY vc.scope_id
        ),
        site_companies AS (
            SELECT
                cp.scope_id::uuid AS site_id,
                STRING_AGG(DISTINCT c.standard_name, ', ') FILTER (
                    WHERE cp.role_code = 'OWNER'
                ) AS owner_names,
                STRING_AGG(DISTINCT c.standard_name, ', ') FILTER (
                    WHERE cp.role_code = 'OPERATOR'
                ) AS operator_names,
                STRING_AGG(DISTINCT c.standard_name, ', ') FILTER (
                    WHERE cp.role_code = 'DEVELOPER'
                ) AS developer_names,
                STRING_AGG(DISTINCT c.standard_name, ', ') FILTER (
                    WHERE cp.role_code = 'DBO_PROVIDER'
                ) AS dbo_provider_names
            FROM company_participation cp
            JOIN company c ON c.company_id = cp.company_id
            WHERE cp.scope_type = 'SITE'
              AND cp.review_status = 'CONFIRMED'
            GROUP BY cp.scope_id
        )
        SELECT
            s.site_id,
            s.site_code,
            s.site_name,
            s.address_standard,
            s.address_raw,
            s.sido,
            s.sigungu,
            s.location_precision,
            s.coordinate_quality,
            s.geom,
            CASE WHEN s.geom IS NULL THEN NULL ELSE ST_Y(s.geom) END AS latitude,
            CASE WHEN s.geom IS NULL THEN NULL ELSE ST_X(s.geom) END AS longitude,
            s.review_status,
            s.public_visible,
            COALESCE(pc.total_project_count, 0) AS total_project_count,
            COALESCE(pc.operating_project_count, 0) AS operating_project_count,
            COALESCE(pc.development_project_count, 0) AS development_project_count,
            COALESCE(pc.on_hold_project_count, 0) AS on_hold_project_count,
            CASE
                WHEN COALESCE(pc.operating_project_count, 0) > 0
                 AND COALESCE(pc.development_project_count, 0) > 0 THEN 'MIXED'
                WHEN COALESCE(pc.operating_project_count, 0) > 0 THEN 'OPERATING'
                WHEN COALESCE(pc.development_project_count, 0) > 0 THEN 'DEVELOPMENT'
                WHEN COALESCE(pc.on_hold_project_count, 0) > 0 THEN 'ON_HOLD'
                ELSE 'UNKNOWN'
            END AS lifecycle_group,
            pc.earliest_rfs_date,
            sc.operating_grid_intake_mw,
            sc.operating_it_load_mw,
            sc.development_grid_intake_mw,
            sc.development_it_load_mw,
            co.owner_names,
            co.operator_names,
            co.developer_names,
            co.dbo_provider_names,
            GREATEST(
                s.updated_at,
                COALESCE(pc.latest_project_update, s.updated_at),
                COALESCE(sc.latest_capacity_update, s.updated_at)
            ) AS latest_data_update
        FROM dc_site s
        LEFT JOIN project_counts pc ON pc.site_id = s.site_id
        LEFT JOIN site_capacity sc ON sc.site_id = s.site_id
        LEFT JOIN site_companies co ON co.site_id = s.site_id
        WHERE s.record_status = 'ACTIVE'
        """
    )

    op.execute(
        """
        CREATE VIEW v_region_status_stats AS
        SELECT
            COALESCE(sido, '미확인') AS sido,
            lifecycle_group,
            COUNT(*) AS site_count,
            SUM(total_project_count) AS project_count,
            SUM(operating_project_count) AS operating_project_count,
            SUM(development_project_count) AS development_project_count,
            SUM(operating_grid_intake_mw) AS operating_grid_intake_mw,
            SUM(operating_it_load_mw) AS operating_it_load_mw,
            SUM(development_grid_intake_mw) AS development_grid_intake_mw,
            SUM(development_it_load_mw) AS development_it_load_mw,
            MAX(latest_data_update) AS latest_data_update
        FROM v_site_map
        GROUP BY COALESCE(sido, '미확인'), lifecycle_group
        """
    )

    op.execute(
        """
        CREATE VIEW v_company_capacity_stats AS
        WITH confirmed_participation AS (
            SELECT DISTINCT
                cp.company_id,
                cp.role_code,
                cp.scope_type,
                cp.scope_id
            FROM company_participation cp
            WHERE cp.review_status = 'CONFIRMED'
              AND cp.role_code IN (
                  'OWNER', 'DEVELOPER', 'OPERATOR', 'DBO_PROVIDER'
              )
        )
        SELECT
            c.company_id,
            c.standard_name AS company_name,
            cp.role_code,
            cp.scope_type,
            vc.capacity_type_code,
            vc.capacity_type_name,
            vc.capacity_stage,
            vc.measurement_basis,
            COUNT(DISTINCT cp.scope_id) AS scope_count,
            SUM(vc.normalized_value_mw) AS total_capacity_mw,
            MAX(vc.updated_at) AS latest_data_update
        FROM confirmed_participation cp
        JOIN company c ON c.company_id = cp.company_id
        JOIN v_capacity_current vc
          ON vc.scope_type = cp.scope_type
         AND vc.scope_id::text = cp.scope_id::text
        WHERE vc.normalized_value_mw IS NOT NULL
          AND vc.capacity_type_code IN (
              'GRID_INTAKE_MW', 'CONTRACT_POWER_MW',
              'IT_LOAD_MW', 'GPU_POWER_MW'
          )
        GROUP BY
            c.company_id,
            c.standard_name,
            cp.role_code,
            cp.scope_type,
            vc.capacity_type_code,
            vc.capacity_type_name,
            vc.capacity_stage,
            vc.measurement_basis
        """
    )

    op.execute(
        """
        CREATE VIEW v_yearly_project_supply AS
        WITH project_rfs AS (
            SELECT
                p.project_id,
                p.project_code,
                p.project_name,
                p.site_id,
                p.status_code,
                COALESCE(p.rfs_date, p.planned_rfs_date) AS reporting_rfs_date,
                CASE
                    WHEN p.rfs_date IS NOT NULL THEN 'ACTUAL'
                    WHEN p.planned_rfs_date IS NOT NULL THEN 'PLANNED'
                    ELSE 'UNKNOWN'
                END AS date_basis
            FROM dc_project p
            WHERE p.record_status = 'ACTIVE'
              AND p.status_code <> 'CANCELLED'
        ),
        project_company AS (
            SELECT DISTINCT
                cp.scope_id::uuid AS project_id,
                cp.company_id,
                cp.role_code
            FROM company_participation cp
            WHERE cp.scope_type = 'PROJECT'
              AND cp.review_status = 'CONFIRMED'
              AND cp.role_code IN (
                  'OWNER', 'DEVELOPER', 'OPERATOR', 'DBO_PROVIDER'
              )
        )
        SELECT
            EXTRACT(YEAR FROM pr.reporting_rfs_date)::integer AS supply_year,
            pr.date_basis,
            COALESCE(c.company_id, 'UNASSIGNED') AS company_id,
            COALESCE(c.standard_name, '사업자 미확인') AS company_name,
            COALESCE(pc.role_code, 'UNASSIGNED') AS role_code,
            vc.capacity_type_code,
            vc.capacity_type_name,
            vc.measurement_basis,
            COUNT(DISTINCT pr.project_id) AS project_count,
            SUM(vc.normalized_value_mw) AS new_supply_mw
        FROM project_rfs pr
        LEFT JOIN project_company pc ON pc.project_id = pr.project_id
        LEFT JOIN company c ON c.company_id = pc.company_id
        LEFT JOIN v_capacity_current vc
          ON vc.scope_type = 'PROJECT'
         AND vc.scope_id = pr.project_id
         AND vc.capacity_type_code IN (
             'GRID_INTAKE_MW', 'IT_LOAD_MW'
         )
        WHERE pr.reporting_rfs_date IS NOT NULL
        GROUP BY
            EXTRACT(YEAR FROM pr.reporting_rfs_date)::integer,
            pr.date_basis,
            COALESCE(c.company_id, 'UNASSIGNED'),
            COALESCE(c.standard_name, '사업자 미확인'),
            COALESCE(pc.role_code, 'UNASSIGNED'),
            vc.capacity_type_code,
            vc.capacity_type_name,
            vc.measurement_basis
        """
    )

    op.execute(
        """
        CREATE VIEW v_collection_latest_status AS
        WITH latest_attempt AS (
            SELECT DISTINCT ON (csr.source_id)
                csr.source_id,
                csr.collection_run_id,
                csr.attempt_no,
                csr.run_status,
                csr.started_at,
                csr.finished_at,
                csr.found_item_count,
                csr.new_item_count,
                csr.updated_item_count,
                csr.error_code,
                csr.error_message,
                csr.next_retry_at
            FROM collection_source_run csr
            ORDER BY
                csr.source_id,
                csr.created_at DESC,
                csr.attempt_no DESC
        )
        SELECT
            sr.source_id,
            sr.source_code,
            sr.source_name,
            sr.source_type,
            sr.default_source_grade,
            sr.collection_method,
            sr.collection_interval,
            sr.terms_review_status,
            sr.active,
            la.collection_run_id,
            la.attempt_no,
            la.run_status AS latest_run_status,
            la.started_at AS latest_started_at,
            la.finished_at AS latest_finished_at,
            la.found_item_count,
            la.new_item_count,
            la.updated_item_count,
            la.error_code,
            la.error_message,
            la.next_retry_at,
            CASE
                WHEN la.finished_at IS NULL THEN NULL
                ELSE CURRENT_TIMESTAMP - la.finished_at
            END AS time_since_last_finish
        FROM source_registry sr
        LEFT JOIN latest_attempt la ON la.source_id = sr.source_id
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_collection_latest_status")
    op.execute("DROP VIEW IF EXISTS v_yearly_project_supply")
    op.execute("DROP VIEW IF EXISTS v_company_capacity_stats")
    op.execute("DROP VIEW IF EXISTS v_region_status_stats")
    op.execute("DROP VIEW IF EXISTS v_site_map")
    op.execute("DROP VIEW IF EXISTS v_capacity_current")
