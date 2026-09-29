#!/usr/bin/env python3
"""Export reviewed, public data-center sites to CSV or GeoJSON."""

from __future__ import annotations

import argparse
import csv
import json
import os
import socket
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import create_engine, text

from src04_rss_collector import load_env_file, resolve_database_url


VERSION = "src10-1.0.0"
EXPORT_COLUMNS = (
    "site_code", "site_name", "address_standard", "sido", "sigungu",
    "latitude", "longitude", "lifecycle_group", "owner_names",
    "operator_names", "operating_it_load_mw", "development_it_load_mw",
    "earliest_rfs_date", "latest_data_update",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="검토 완료 공개 센터 현황 추출")
    parser.add_argument("--format", choices=("csv", "geojson"), default="csv")
    parser.add_argument("--sido")
    parser.add_argument(
        "--status",
        choices=("OPERATING", "DEVELOPMENT", "MIXED", "ON_HOLD", "UNKNOWN"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--requested-by", default=os.getenv("USER", "dc-platform"))
    parser.add_argument("--purpose", default="공개 데이터센터 현황 확인")
    return parser.parse_args()


def build_site_query(sido: str | None, status: str | None) -> tuple[str, dict[str, str]]:
    conditions = ["public_visible = true", "review_status = 'CONFIRMED'"]
    parameters: dict[str, str] = {}
    if sido:
        conditions.append("sido = :sido")
        parameters["sido"] = sido
    if status:
        conditions.append("lifecycle_group = :status")
        parameters["status"] = status
    columns = ", ".join(EXPORT_COLUMNS)
    query = (
        f"SELECT {columns} FROM v_site_map WHERE "
        + " AND ".join(conditions)
        + " ORDER BY sido NULLS LAST, sigungu NULLS LAST, site_name"
    )
    return query, parameters


def json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def safe_csv_value(value: Any) -> Any:
    if value is None:
        return ""
    value = json_value(value)
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: safe_csv_value(row.get(key)) for key in EXPORT_COLUMNS})
            count += 1
    return count


def to_feature(row: dict[str, Any]) -> dict[str, Any]:
    latitude = row.get("latitude")
    longitude = row.get("longitude")
    geometry = None
    if latitude is not None and longitude is not None:
        geometry = {"type": "Point", "coordinates": [float(longitude), float(latitude)]}
    properties = {
        key: json_value(row.get(key))
        for key in EXPORT_COLUMNS
        if key not in {"latitude", "longitude"}
    }
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def write_geojson(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    features = [to_feature(row) for row in rows]
    path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        encoding="utf-8",
    )
    return len(features)


def create_export_job(
    engine: Any, requested_by: str, purpose: str, export_format: str,
    filters: dict[str, Any], path: Path,
) -> Any:
    with engine.begin() as connection:
        return connection.execute(
            text(
                """
                INSERT INTO export_job (
                    requested_by, requested_role, purpose, export_format,
                    access_scope, filters_json, columns_json, job_status,
                    storage_path, started_at
                ) VALUES (
                    :requested_by, 'ANALYST', :purpose, :export_format,
                    'PUBLIC', CAST(:filters AS jsonb), CAST(:columns AS jsonb),
                    'RUNNING', :storage_path, CURRENT_TIMESTAMP
                ) RETURNING export_job_id
                """
            ),
            {
                "requested_by": requested_by[:150],
                "purpose": purpose,
                "export_format": export_format,
                "filters": json.dumps(filters, ensure_ascii=False),
                "columns": json.dumps(EXPORT_COLUMNS),
                "storage_path": str(path),
            },
        ).scalar_one()


def finish_export_job(
    engine: Any, job_id: Any, requested_by: str, path: Path,
    row_count: int | None, error: Exception | None,
) -> None:
    status = "FAILED" if error else "SUCCESS"
    error_name = type(error).__name__ if error else None
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE export_job
                SET job_status = :status, row_count = :row_count,
                    completed_at = CURRENT_TIMESTAMP, error_message = :error,
                    updated_at = CURRENT_TIMESTAMP
                WHERE export_job_id = :job_id
                """
            ),
            {"job_id": job_id, "status": status, "row_count": row_count, "error": error_name},
        )
        connection.execute(
            text(
                """
                INSERT INTO audit_log (
                    actor_id, role_at_action, action, entity_type, entity_id,
                    reason, export_job_id, export_fields, export_row_count,
                    result, error_code
                ) VALUES (
                    :actor, 'ANALYST', :action, 'EXPORT_JOB', :entity_id,
                    :reason, :job_id, CAST(:fields AS jsonb), :row_count,
                    :result, :error_code
                )
                """
            ),
            {
                "actor": requested_by[:150],
                "action": "PUBLIC_EXPORT_FAILED" if error else "PUBLIC_EXPORT_CREATED",
                "entity_id": str(job_id),
                "reason": error_name if error else "Reviewed public site export",
                "job_id": job_id,
                "fields": json.dumps(EXPORT_COLUMNS),
                "row_count": row_count,
                "result": "FAILED" if error else "SUCCESS",
                "error_code": error_name,
            },
        )


def default_output(export_format: str) -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    return Path("data/exports") / f"public_sites_{stamp}.{export_format}"


def main() -> int:
    load_env_file()
    args = parse_args()
    output = (args.output or default_output(args.format)).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    filters = {key: value for key, value in {"sido": args.sido, "status": args.status}.items() if value}
    engine = create_engine(resolve_database_url(), pool_pre_ping=True)
    job_id = None
    try:
        job_id = create_export_job(
            engine, args.requested_by, args.purpose, args.format.upper(), filters, output
        )
        query, parameters = build_site_query(args.sido, args.status)
        with engine.connect() as connection:
            rows = [dict(row) for row in connection.execute(text(query), parameters).mappings()]
        row_count = write_csv(temporary, rows) if args.format == "csv" else write_geojson(temporary, rows)
        temporary.replace(output)
        finish_export_job(engine, job_id, args.requested_by, output, row_count, None)
        print(f"공개 센터 {row_count}건 추출: {output}")
        return 0
    except Exception as error:
        temporary.unlink(missing_ok=True)
        if job_id is not None:
            finish_export_job(engine, job_id, args.requested_by, output, None, error)
        print(f"추출 실패: {type(error).__name__}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
