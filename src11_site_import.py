#!/usr/bin/env python3
"""Validate and optionally import data-center site baseline CSV files."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from src04_rss_collector import load_env_file, resolve_database_url


REQUIRED_COLUMNS = ("site_code", "site_name", "address_raw")
ALL_COLUMNS = REQUIRED_COLUMNS + (
    "address_standard", "sido", "sigungu", "latitude", "longitude",
    "location_precision", "coordinate_quality",
)
SITE_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,29}$")
PRECISIONS = {"ROOFTOP", "PARCEL", "ROAD", "DISTRICT", "CITY", "UNKNOWN"}
QUALITIES = {"A", "B", "C", "D", "U"}


@dataclass(frozen=True)
class ValidationError:
    row: int
    field: str
    message: str


def clean(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def validate_rows(fieldnames: list[str] | None, raw_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[ValidationError]]:
    errors: list[ValidationError] = []
    missing = [name for name in REQUIRED_COLUMNS if name not in (fieldnames or [])]
    if missing:
        return [], [ValidationError(1, name, "필수 열 누락") for name in missing]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for number, raw in enumerate(raw_rows, start=2):
        row = {key: clean(raw.get(key)) for key in ALL_COLUMNS}
        for field in REQUIRED_COLUMNS:
            if not row[field]:
                errors.append(ValidationError(number, field, "필수값 누락"))
        if row["site_code"] and not SITE_CODE.fullmatch(row["site_code"]):
            errors.append(ValidationError(number, "site_code", "영문 대문자·숫자·_- 형식 필요"))
        if row["site_code"] in seen:
            errors.append(ValidationError(number, "site_code", "파일 내 중복"))
        seen.add(row["site_code"])
        precision = row["location_precision"] or "UNKNOWN"
        quality = row["coordinate_quality"] or "U"
        if precision not in PRECISIONS:
            errors.append(ValidationError(number, "location_precision", "허용되지 않은 값"))
        if quality not in QUALITIES:
            errors.append(ValidationError(number, "coordinate_quality", "허용되지 않은 값"))
        latitude = longitude = None
        try:
            latitude = float(row["latitude"]) if row["latitude"] else None
            longitude = float(row["longitude"]) if row["longitude"] else None
        except ValueError:
            errors.append(ValidationError(number, "coordinates", "숫자 형식 필요"))
        if (latitude is None) != (longitude is None):
            errors.append(ValidationError(number, "coordinates", "위도·경도를 함께 입력"))
        if latitude is not None and not (33 <= latitude <= 39.5 and 124 <= longitude <= 132):
            errors.append(ValidationError(number, "coordinates", "대한민국 좌표 범위 확인 필요"))
        rows.append({**row, "latitude": latitude, "longitude": longitude,
                     "location_precision": precision, "coordinate_quality": quality})
    return rows, errors


def read_csv(path: Path) -> tuple[list[dict[str, Any]], list[ValidationError]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        raw_rows = list(reader)
        return validate_rows(reader.fieldnames, raw_rows)


def import_rows(engine: Any, rows: list[dict[str, Any]]) -> int:
    inserted = 0
    with engine.begin() as connection:
        for row in rows:
            result = connection.execute(text("""
                INSERT INTO dc_site (
                    site_code, site_name, address_raw, address_standard, sido,
                    sigungu, location_precision, coordinate_quality, geom,
                    review_status, public_visible
                ) VALUES (
                    :site_code, :site_name, :address_raw, NULLIF(:address_standard,''),
                    NULLIF(:sido,''), NULLIF(:sigungu,''), :location_precision,
                    :coordinate_quality,
                    CASE WHEN :latitude IS NULL THEN NULL ELSE ST_SetSRID(ST_MakePoint(:longitude,:latitude),4326) END,
                    'NEEDS_EVIDENCE', false
                ) ON CONFLICT (site_code) DO NOTHING
            """), row)
            inserted += result.rowcount
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="센터 기준 데이터 CSV 검증·반입")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rows, errors = read_csv(args.csv_file)
    if errors:
        for error in errors[:50]:
            print(f"행 {error.row} {error.field}: {error.message}", file=sys.stderr)
        print(f"검증 실패: {len(errors)}건", file=sys.stderr)
        return 2
    print(f"검증 성공: {len(rows)}건")
    if not args.apply:
        print("dry-run 완료: DB를 변경하지 않았습니다.")
        return 0
    load_env_file()
    engine = create_engine(resolve_database_url(), pool_pre_ping=True)
    try:
        inserted = import_rows(engine, rows)
    finally:
        engine.dispose()
    print(f"반입 완료: 신규 {inserted}건, 중복 {len(rows)-inserted}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
