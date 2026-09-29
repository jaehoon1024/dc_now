#!/usr/bin/env python3
"""Validate and optionally import data-center project baseline CSV files."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from src04_rss_collector import load_env_file, resolve_database_url


REQUIRED_COLUMNS = ("project_code", "site_code", "project_name", "project_scope")
ALL_COLUMNS = REQUIRED_COLUMNS + (
    "project_type", "status_code", "scope_note", "planned_rfs_date",
    "rfs_date", "completion_date", "service_start_date",
)
CODE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,29}$")
STATUSES = {
    "", "IDEA", "SITE_SECURED", "PERMITTING", "POWER_SECURED",
    "CONSTRUCTION", "READY", "OPERATING", "ON_HOLD", "CANCELLED",
}
DATE_FIELDS = (
    "planned_rfs_date", "rfs_date", "completion_date", "service_start_date",
)


@dataclass(frozen=True)
class ValidationError:
    row: int
    field: str
    message: str


def clean(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def parse_date(value: str, row: int, field: str, errors: list[ValidationError]) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(ValidationError(row, field, "YYYY-MM-DD 형식 필요"))
        return None


def validate_rows(
    fieldnames: list[str] | None, raw_rows: list[dict[str, str]]
) -> tuple[list[dict[str, Any]], list[ValidationError]]:
    missing = [name for name in REQUIRED_COLUMNS if name not in (fieldnames or [])]
    if missing:
        return [], [ValidationError(1, name, "필수 열 누락") for name in missing]
    rows: list[dict[str, Any]] = []
    errors: list[ValidationError] = []
    seen: set[str] = set()
    for number, raw in enumerate(raw_rows, start=2):
        row: dict[str, Any] = {key: clean(raw.get(key)) for key in ALL_COLUMNS}
        for field in REQUIRED_COLUMNS:
            if not row[field]:
                errors.append(ValidationError(number, field, "필수값 누락"))
        for field in ("project_code", "site_code"):
            if row[field] and not CODE.fullmatch(row[field]):
                errors.append(ValidationError(number, field, "영문 대문자·숫자·_- 형식 필요"))
        if row["project_code"] in seen:
            errors.append(ValidationError(number, "project_code", "파일 내 중복"))
        seen.add(row["project_code"])
        if row["status_code"] not in STATUSES:
            errors.append(ValidationError(number, "status_code", "허용되지 않은 상태"))
        for field in DATE_FIELDS:
            row[field] = parse_date(row[field], number, field, errors)
        completion = row["completion_date"]
        rfs = row["rfs_date"]
        service = row["service_start_date"]
        if completion and rfs and completion > rfs:
            errors.append(ValidationError(number, "rfs_date", "준공일보다 빠를 수 없음"))
        if completion and service and completion > service:
            errors.append(ValidationError(number, "service_start_date", "준공일보다 빠를 수 없음"))
        rows.append(row)
    return rows, errors


def read_csv(path: Path) -> tuple[list[dict[str, Any]], list[ValidationError]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return validate_rows(reader.fieldnames, list(reader))


def missing_site_codes(engine: Any, rows: list[dict[str, Any]]) -> set[str]:
    requested = {row["site_code"] for row in rows if row["site_code"]}
    if not requested:
        return set()
    with engine.connect() as connection:
        existing = set(connection.execute(
            text("SELECT site_code FROM dc_site WHERE site_code = ANY(:codes) AND record_status = 'ACTIVE'"),
            {"codes": list(requested)},
        ).scalars())
    return requested - existing


def import_rows(engine: Any, rows: list[dict[str, Any]]) -> int:
    inserted = 0
    with engine.begin() as connection:
        for row in rows:
            result = connection.execute(text("""
                INSERT INTO dc_project (
                    project_code, site_id, project_name, project_type,
                    project_scope, status_code, scope_note, planned_rfs_date,
                    rfs_date, completion_date, service_start_date,
                    review_status, public_visible
                ) SELECT
                    :project_code, s.site_id, :project_name,
                    NULLIF(:project_type,''), :project_scope,
                    NULLIF(:status_code,''), NULLIF(:scope_note,''),
                    :planned_rfs_date, :rfs_date, :completion_date,
                    :service_start_date, 'NEEDS_EVIDENCE', false
                FROM dc_site s WHERE s.site_code = :site_code
                  AND s.record_status = 'ACTIVE'
                ON CONFLICT (project_code) DO NOTHING
            """), row)
            inserted += result.rowcount
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="프로젝트 기준 데이터 CSV 검증·반입")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rows, errors = read_csv(args.csv_file)
    if errors:
        for error in errors[:50]:
            print(f"행 {error.row} {error.field}: {error.message}", file=sys.stderr)
        print(f"검증 실패: {len(errors)}건", file=sys.stderr)
        return 2
    load_env_file()
    engine = create_engine(resolve_database_url(), pool_pre_ping=True)
    try:
        missing = missing_site_codes(engine, rows)
        if missing:
            print("존재하지 않는 센터 코드: " + ", ".join(sorted(missing)), file=sys.stderr)
            return 2
        print(f"검증 성공: {len(rows)}건")
        if not args.apply:
            print("dry-run 완료: DB를 변경하지 않았습니다.")
            return 0
        inserted = import_rows(engine, rows)
        print(f"반입 완료: 신규 {inserted}건, 중복 {len(rows)-inserted}건")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
