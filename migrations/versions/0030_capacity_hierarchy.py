"""Include public project/phase capacities without counting parent totals twice."""
from typing import Sequence, Union
from alembic import op
revision: str = "0030_capacity_hierarchy"
down_revision: Union[str, None] = "0029_enterprise_data_centers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
CREATE OR REPLACE VIEW v_site_map AS
WITH eligible_projects AS (
 SELECT * FROM dc_project WHERE record_status='ACTIVE' AND deleted_at IS NULL
 AND review_status='CONFIRMED' AND public_visible AND status_code<>'CANCELLED'
), project_counts AS (
 SELECT site_id,COUNT(*) AS total_project_count,
 COUNT(*) FILTER(WHERE status_code='OPERATING') AS operating_project_count,
 COUNT(*) FILTER(WHERE status_code IN ('IDEA','SITE_SECURED','PERMITTING','POWER_SECURED','CONSTRUCTION','READY')) AS development_project_count,
 COUNT(*) FILTER(WHERE status_code='ON_HOLD') AS on_hold_project_count,
 MIN(COALESCE(rfs_date,planned_rfs_date)) AS earliest_rfs_date,
 MAX(updated_at) AS latest_project_update FROM eligible_projects GROUP BY site_id
), latest AS (
 SELECT DISTINCT ON (vc.scope_type,vc.scope_id,vc.capacity_type_code,
   CASE WHEN vc.capacity_stage='OPERATING' THEN 'OPERATING' ELSE 'DEVELOPMENT' END)
 vc.*, CASE WHEN vc.capacity_stage='OPERATING' THEN 'OPERATING' ELSE 'DEVELOPMENT' END AS bucket
 FROM capacity_snapshot vc
 WHERE vc.review_status='CONFIRMED' AND NOT vc.aggregation_excluded
 AND (vc.effective_from IS NULL OR vc.effective_from<=CURRENT_DATE)
 AND (vc.effective_to IS NULL OR vc.effective_to>=CURRENT_DATE) AND vc.capacity_type_code IN ('IT_LOAD_MW','GRID_INTAKE_MW')
 AND vc.measurement_basis='PUBLISHED_CAPACITY' AND vc.normalized_value_mw IS NOT NULL
 AND EXISTS (SELECT 1 FROM evidence_document ed WHERE ed.canonical_url=vc.document_url AND ed.access_scope='PUBLIC' AND ed.review_status='CONFIRMED' AND ed.record_status='ACTIVE')
 ORDER BY vc.scope_type,vc.scope_id,vc.capacity_type_code,
 CASE WHEN vc.capacity_stage='OPERATING' THEN 'OPERATING' ELSE 'DEVELOPMENT' END,
 vc.effective_from DESC NULLS LAST, vc.published_at DESC NULLS LAST,vc.updated_at DESC,
 CASE vc.capacity_stage WHEN 'OPERATING' THEN 6 WHEN 'INSTALLED' THEN 5
 WHEN 'UNDER_CONSTRUCTION' THEN 4 WHEN 'DESIGNED' THEN 3 WHEN 'SECURED' THEN 2 ELSE 1 END DESC,
 vc.capacity_id
), phase_totals AS (
 SELECT p.site_id,p.project_id,l.capacity_type_code,l.bucket,SUM(l.normalized_value_mw) AS mw,MAX(l.updated_at) AS updated_at
 FROM latest l JOIN project_phase ph ON l.scope_type='PHASE' AND l.scope_id=ph.phase_id
 JOIN eligible_projects p ON p.project_id=ph.project_id
 WHERE ph.record_status='ACTIVE' AND ph.deleted_at IS NULL AND ph.review_status='CONFIRMED'
 AND ph.status_code NOT IN ('CANCELLED','ON_HOLD') AND p.status_code<>'ON_HOLD'
 GROUP BY p.site_id,p.project_id,l.capacity_type_code,l.bucket
), project_values AS (
 SELECT p.site_id,p.project_id,l.capacity_type_code,l.bucket,l.normalized_value_mw AS mw,l.updated_at
 FROM latest l JOIN eligible_projects p ON l.scope_type='PROJECT' AND l.scope_id=p.project_id
 WHERE p.status_code<>'ON_HOLD'
 UNION ALL
 SELECT ph.* FROM phase_totals ph WHERE NOT EXISTS (
 SELECT 1 FROM latest l WHERE l.scope_type='PROJECT' AND l.scope_id=ph.project_id
 AND l.capacity_type_code=ph.capacity_type_code AND l.bucket=ph.bucket)
), site_values AS (
 SELECT l.scope_id::uuid AS site_id,l.capacity_type_code,l.bucket,l.normalized_value_mw AS mw,l.updated_at
 FROM latest l WHERE l.scope_type='SITE'
 UNION ALL
 SELECT p.site_id,p.capacity_type_code,p.bucket,SUM(p.mw),MAX(p.updated_at)
 FROM project_values p WHERE NOT EXISTS (
 SELECT 1 FROM latest l WHERE l.scope_type='SITE' AND l.scope_id=p.site_id
 AND l.capacity_type_code=p.capacity_type_code AND l.bucket=p.bucket)
 GROUP BY p.site_id,p.capacity_type_code,p.bucket
), site_capacity AS (
 SELECT site_id,
 MAX(mw) FILTER(WHERE capacity_type_code='GRID_INTAKE_MW' AND bucket='OPERATING') AS operating_grid_intake_mw,
 MAX(mw) FILTER(WHERE capacity_type_code='IT_LOAD_MW' AND bucket='OPERATING') AS operating_it_load_mw,
 MAX(mw) FILTER(WHERE capacity_type_code='GRID_INTAKE_MW' AND bucket='DEVELOPMENT') AS development_grid_intake_mw,
 MAX(mw) FILTER(WHERE capacity_type_code='IT_LOAD_MW' AND bucket='DEVELOPMENT') AS development_it_load_mw,
 MAX(updated_at) AS latest_capacity_update FROM site_values GROUP BY site_id
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
              AND cp.review_status = 'CONFIRMED' AND cp.public_visible=true
              AND c.review_status='CONFIRMED' AND c.record_status='ACTIVE'
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

DOWNGRADE_SQL = """
CREATE OR REPLACE VIEW v_site_map AS
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

def upgrade():
    op.execute(UPGRADE_SQL)

def downgrade():
    op.execute(DOWNGRADE_SQL)
