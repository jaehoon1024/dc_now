#!/usr/bin/env python3
"""Resolve exact parcel coordinates from the public Google Maps embed result.

The response includes both a resolved English address and its point.  A result
is accepted only when the parcel number exactly matches and the resolved
province/city agrees with the stored Korean address.
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
from src22_geocode_sites import KOREA_BOUNDS, apply_rows
from src23_kakao_address_geocoder import parcel_key


ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://maps.google.com/maps"
DEFAULT_CACHE = ROOT / "data" / "cache" / "google_embed_geocode.json"
DEFAULT_OUTPUT = ROOT / "data" / "verified_google_parcel_coordinates_20261003.csv"
USER_AGENT = "Mozilla/5.0 (compatible; dc-now-location-review/1.0)"
ENTITY_RE = re.compile(
    r'\["0x[0-9a-f]+:[^"\\]+","(?P<address>[^"\\]+)",'
    r'\[(?P<lat>-?\d+\.\d+),(?P<lon>-?\d+\.\d+)\]\]'
)

REGION_TOKENS = {
    "서울특별시": ("Seoul",),
    "부산광역시": ("Busan",),
    "인천광역시": ("Incheon",),
    "대구광역시": ("Daegu",),
    "대전광역시": ("Daejeon",),
    "광주광역시": ("Gwangju",),
    "울산광역시": ("Ulsan",),
    "세종특별자치시": ("Sejong",),
    "경기도": ("Gyeonggi",),
    "강원특별자치도": ("Gangwon",),
    "충청북도": ("Chungcheongbuk", "North Chungcheong"),
    "충청남도": ("Chungcheongnam", "South Chungcheong"),
    "전북특별자치도": ("Jeonbuk", "North Jeolla"),
    "전라남도": ("Jeonnam", "South Jeolla"),
    "경상북도": ("Gyeongsangbuk", "North Gyeongsang"),
    "경상남도": ("Gyeongsangnam", "South Gyeongsang"),
    "제주특별자치도": ("Jeju",),
}


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch(query: str, timeout: int = 20) -> dict[str, Any]:
    url = ENDPOINT + "?" + urlencode({"q": query, "output": "embed"})
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
    with urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
    match = ENTITY_RE.search(html)
    if not match:
        return {}
    return {
        "resolved_address": match.group("address"),
        "latitude": match.group("lat"),
        "longitude": match.group("lon"),
    }


def exact_result(site: dict[str, Any], result: dict[str, Any]) -> bool:
    key = parcel_key(str(site.get("address_standard") or ""))
    if not key or not result:
        return False
    _, lot = key
    resolved = str(result.get("resolved_address") or "")
    if not re.search(rf"(?:^|\s){re.escape(lot)}(?:\s|,|$)", resolved):
        return False
    region_tokens = REGION_TOKENS.get(str(site.get("sido") or ""), ())
    if region_tokens and not any(token.lower() in resolved.lower() for token in region_tokens):
        return False
    try:
        lat, lon = float(result["latitude"]), float(result["longitude"])
    except (KeyError, TypeError, ValueError):
        return False
    south, north, west, east = KOREA_BOUNDS
    return south <= lat <= north and west <= lon <= east


def load_sites(engine: Any) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        return [
            dict(row) for row in connection.execute(
                text(
                    """
                    SELECT site_code, site_name, address_standard, sido, sigungu,
                           location_precision
                    FROM dc_site
                    WHERE record_status = 'ACTIVE'
                      AND geom IS NULL
                      AND location_precision = 'PARCEL'
                    ORDER BY site_code
                    """
                )
            ).mappings()
        ]


def build_rows(sites: list[dict[str, Any]], cache: dict[str, dict[str, Any]], delay: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    requested = False
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    for index, site in enumerate(sites, start=1):
        query = str(site["address_standard"])
        if query not in cache:
            if requested:
                time.sleep(delay)
            cache[query] = fetch(query)
            requested = True
        result = cache[query]
        accepted = exact_result(site, result)
        if accepted:
            map_url = ENDPOINT + "?" + urlencode({"q": query})
            rows.append(
                {
                    "site_code": site["site_code"],
                    "site_name": site["site_name"],
                    "address_standard": query,
                    "sido": site.get("sido") or "",
                    "sigungu": site.get("sigungu") or "",
                    "latitude": result["latitude"],
                    "longitude": result["longitude"],
                    "location_precision": "PARCEL",
                    "coordinate_quality": "B",
                    "provider": "Google Maps embed address result",
                    "provider_result_type": "exact_parcel_address",
                    "provider_display_name": result["resolved_address"],
                    "geocoded_at": stamp,
                    "address_source_url": map_url,
                    "coordinate_source_url": map_url,
                }
            )
        print(f"[{index}/{len(sites)}] {site['site_code']}: {'MATCH' if accepted else 'NO_MATCH'}", flush=True)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "site_code", "site_name", "address_standard", "sido", "sigungu",
        "latitude", "longitude", "location_precision", "coordinate_quality",
        "provider", "provider_result_type", "provider_display_name", "geocoded_at",
        "address_source_url", "coordinate_source_url",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Google 지도 임베드 필지 좌표 검토")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--delay", type=float, default=1.2)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    load_env_file()
    engine = create_engine(resolve_database_url(), pool_pre_ping=True)
    try:
        sites = load_sites(engine)
        cache = load_cache(args.cache)
        rows = build_rows(sites, cache, args.delay)
        save_cache(args.cache, cache)
        write_csv(args.output, rows)
        print(f"검토 파일: {args.output} ({len(rows)}/{len(sites)}건 정확 일치)")
        if args.apply:
            print(f"DB 반영: {apply_rows(engine, rows)}건")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
