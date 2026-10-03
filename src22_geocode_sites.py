#!/usr/bin/env python3
"""Geocode missing data-center coordinates without overwriting known points.

The command uses the public Nominatim endpoint at a deliberately slow rate,
caches every response, and can either write a review CSV or apply accepted
matches to rows whose geometry is still NULL.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, text

from src04_rss_collector import load_env_file, resolve_database_url


ROOT = Path(__file__).resolve().parent
DEFAULT_CACHE = ROOT / "data" / "cache" / "nominatim_geocode.json"
DEFAULT_OUTPUT = ROOT / "data" / "geocoded_sites_20261003.csv"
ENDPOINT = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "dc-now-market-intelligence/1.0 (github.com/jaehoon1024/dc_now)"
KOREA_BOUNDS = (33.0, 39.5, 124.0, 132.0)
EXACT_PRECISIONS = {"ROOFTOP", "PARCEL", "ROAD"}


def load_cache(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: dict[str, list[dict[str, Any]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch(query: str, timeout: int = 20) -> list[dict[str, Any]]:
    url = ENDPOINT + "?" + urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": 5,
            "countrycodes": "kr",
            "addressdetails": 1,
        }
    )
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ko,en"})
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def in_korea(result: dict[str, Any]) -> bool:
    try:
        lat, lon = float(result["lat"]), float(result["lon"])
    except (KeyError, TypeError, ValueError):
        return False
    south, north, west, east = KOREA_BOUNDS
    return south <= lat <= north and west <= lon <= east


def normalized(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def choose_result(site: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [
        result for result in results
        if in_korea(result)
        and str(result.get("addresstype") or result.get("type") or "") != "country"
    ]
    if not valid:
        return None
    sido = normalized(site.get("sido"))
    sigungu = normalized(site.get("sigungu"))

    def score(result: dict[str, Any]) -> tuple[int, float]:
        display = normalized(result.get("display_name"))
        address = result.get("address") or {}
        result_type = str(result.get("addresstype") or result.get("type") or "")
        value = 0
        if sigungu and sigungu != "미확인" and sigungu in display:
            value += 8
        if sido and sido in display:
            value += 4
        if str(address.get("country_code") or "").lower() == "kr":
            value += 2
        if result_type in {"house", "building", "amenity", "office", "industrial"}:
            value += 3
        elif result_type in {"road", "residential", "neighbourhood", "quarter"}:
            value += 1
        return value, float(result.get("importance") or 0)

    selected = max(valid, key=score)
    selected_score, _ = score(selected)
    required = 6 if sigungu and sigungu != "미확인" else 2
    return selected if selected_score >= required else None


def coordinate_quality(site: dict[str, Any], result: dict[str, Any]) -> str:
    precision = str(site.get("location_precision") or "UNKNOWN")
    result_type = str(result.get("addresstype") or result.get("type") or "")
    address = normalized(site.get("address_standard"))
    display = normalized(result.get("display_name"))
    road_tokens = [
        normalized(token)
        for token in str(site.get("address_standard") or "").split()
        if re.search(r"(?:대로|로|길)", token)
    ]
    numbers = re.findall(r"\d+(?:-\d+)?", address)
    detailed_result = result_type in {"house", "building", "amenity", "office", "industrial"}
    if (
        precision == "ROAD"
        and detailed_result
        and road_tokens
        and any(token in display for token in road_tokens)
        and numbers
        and numbers[-1] in display
    ):
        return "C"
    return "D"


def geocode_sites(
    sites: list[dict[str, Any]],
    cache: dict[str, list[dict[str, Any]]],
    delay: float,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    uncached_request = False
    for index, site in enumerate(sites, start=1):
        query = str(site.get("address_standard") or site.get("address_raw") or "").strip()
        if not query:
            continue
        if query not in cache:
            if uncached_request:
                time.sleep(delay)
            cache[query] = fetch(query)
            uncached_request = True
        result = choose_result(site, cache[query])
        if result:
            output.append(
                {
                    "site_code": site["site_code"],
                    "site_name": site["site_name"],
                    "address_standard": query,
                    "sido": site.get("sido") or "",
                    "sigungu": site.get("sigungu") or "",
                    "latitude": result["lat"],
                    "longitude": result["lon"],
                    "location_precision": site.get("location_precision") or "UNKNOWN",
                    "coordinate_quality": coordinate_quality(site, result),
                    "provider": "OpenStreetMap Nominatim",
                    "provider_result_type": result.get("addresstype") or result.get("type") or "",
                    "provider_display_name": result.get("display_name") or "",
                    "geocoded_at": datetime.now().astimezone().isoformat(),
                }
            )
        print(f"[{index}/{len(sites)}] {site['site_code']}: {'MATCH' if result else 'NO_MATCH'}", flush=True)
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "site_code", "site_name", "address_standard", "sido", "sigungu",
        "latitude", "longitude", "location_precision", "coordinate_quality",
        "provider", "provider_result_type", "provider_display_name", "geocoded_at",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def apply_rows(engine: Any, rows: list[dict[str, Any]]) -> int:
    updated = 0
    statement = text(
        """
        UPDATE dc_site
        SET geom = ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326),
            address_standard = COALESCE(NULLIF(:address_standard, ''), address_standard),
            location_precision = COALESCE(NULLIF(:location_precision, ''), location_precision),
            coordinate_quality = :coordinate_quality,
            updated_at = CURRENT_TIMESTAMP
        WHERE site_code = :site_code
          AND geom IS NULL
        """
    )
    with engine.begin() as connection:
        for row in rows:
            updated += connection.execute(statement, row).rowcount
    return updated


def load_missing_sites(engine: Any, exact_only: bool, limit: int | None) -> list[dict[str, Any]]:
    where = "AND location_precision IN ('ROOFTOP','PARCEL','ROAD')" if exact_only else ""
    limit_sql = "LIMIT :limit" if limit else ""
    statement = text(
        f"""
        SELECT site_code, site_name, address_raw, address_standard, sido, sigungu,
               location_precision, coordinate_quality
        FROM dc_site
        WHERE record_status = 'ACTIVE' AND geom IS NULL {where}
        ORDER BY CASE WHEN location_precision IN ('ROOFTOP','PARCEL','ROAD') THEN 0 ELSE 1 END,
                 site_code
        {limit_sql}
        """
    )
    params = {"limit": limit} if limit else {}
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(statement, params).mappings()]


def main() -> int:
    parser = argparse.ArgumentParser(description="빈 데이터센터 좌표를 공개 주소로 보강")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--delay", type=float, default=1.1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--exact-only", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--allow-approximate",
        action="store_true",
        help="D등급 행정구역·도로 중심 좌표도 반영 (기본값은 C등급만 반영)",
    )
    args = parser.parse_args()
    load_env_file()
    engine = create_engine(resolve_database_url(), pool_pre_ping=True)
    try:
        sites = load_missing_sites(engine, args.exact_only, args.limit)
        cache = load_cache(args.cache)
        rows = geocode_sites(sites, cache, args.delay)
        save_cache(args.cache, cache)
        write_csv(args.output, rows)
        print(f"검토 파일: {args.output} ({len(rows)}/{len(sites)}건 매칭)")
        if args.apply:
            accepted = rows if args.allow_approximate else [
                row for row in rows if row["coordinate_quality"] in {"A", "B", "C"}
            ]
            print(f"DB 반영: {apply_rows(engine, accepted)}건 (D등급 보류 {len(rows)-len(accepted)}건)")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
