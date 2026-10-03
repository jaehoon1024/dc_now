#!/usr/bin/env python3
"""Resolve exact Korean parcel addresses through Kakao Map public search.

Only results whose legal-dong/eup/myeon and parcel number exactly match the
stored address are accepted.  The script writes an auditable review CSV and
never replaces an existing geometry.
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


ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://search.map.kakao.com/mapsearch/map.daum"
DEFAULT_CACHE = ROOT / "data" / "cache" / "kakao_address_geocode.json"
DEFAULT_OUTPUT = ROOT / "data" / "verified_parcel_coordinates_20261003.csv"
USER_AGENT = "Mozilla/5.0 (compatible; dc-now-location-review/1.0)"
PARCEL_RE = re.compile(r"(?P<locality>[^\s]+(?:동|읍|면|리|가))\s+(?:산\s*)?(?P<lot>\d+(?:-\d+)?)$")


def load_cache(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch(query: str, timeout: int = 20) -> dict[str, Any]:
    url = ENDPOINT + "?" + urlencode({"q": query})
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Referer": "https://map.kakao.com/",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def parcel_key(address: str) -> tuple[str, str] | None:
    match = PARCEL_RE.search(address.strip())
    if not match:
        return None
    return match.group("locality"), match.group("lot")


def exact_parcel_match(address: str, candidate: str) -> bool:
    key = parcel_key(address)
    if not key:
        return False
    locality, lot = key
    if locality not in candidate:
        return False
    return re.search(rf"{re.escape(locality)}\s+(?:산\s*)?{re.escape(lot)}(?:\s|$)", candidate) is not None


def in_korea(place: dict[str, Any]) -> bool:
    try:
        lat, lon = float(place["lat"]), float(place["lon"])
    except (KeyError, TypeError, ValueError):
        return False
    south, north, west, east = KOREA_BOUNDS
    return south <= lat <= north and west <= lon <= east


def choose_place(site: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
    address = str(site.get("address_standard") or "")
    matches = [
        place for place in payload.get("place", [])
        if in_korea(place) and exact_parcel_match(address, str(place.get("address") or ""))
    ]
    if not matches:
        return None
    data_center_words = ("데이터센터", "IDC", "전산", "클라우드", "센터")
    return max(matches, key=lambda place: sum(word.lower() in str(place.get("name") or "").lower() for word in data_center_words))


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
        place = choose_place(site, cache[query])
        if place:
            map_url = "https://map.kakao.com/?" + urlencode({"q": query})
            rows.append(
                {
                    "site_code": site["site_code"],
                    "site_name": site["site_name"],
                    "address_standard": query,
                    "sido": site.get("sido") or "",
                    "sigungu": site.get("sigungu") or "",
                    "latitude": place["lat"],
                    "longitude": place["lon"],
                    "location_precision": "PARCEL",
                    "coordinate_quality": "B",
                    "provider": "Kakao Map public search",
                    "provider_result_type": "exact_parcel_place",
                    "provider_display_name": place.get("name") or place.get("address") or "",
                    "geocoded_at": stamp,
                    "address_source_url": map_url,
                    "coordinate_source_url": map_url,
                }
            )
        print(f"[{index}/{len(sites)}] {site['site_code']}: {'MATCH' if place else 'NO_MATCH'}", flush=True)
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
    parser = argparse.ArgumentParser(description="필지 주소 기반 데이터센터 좌표 검토")
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
