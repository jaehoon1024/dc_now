#!/usr/bin/env python3
"""Backfill approved Google News metadata in bounded date windows.

Google News RSS limits the number of results returned for a broad query.  This
collector splits a historical range into smaller windows, then sends every
item through the normal RSS metadata store and duplicate checks.  Article
bodies are never downloaded or stored.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine

import src04_rss_collector as rss


VERSION = "src25-1.0.0"
DEFAULT_FEEDS = (
    "GNEWS_DC_COMMERCIAL",
    "GNEWS_DC_DEVELOPMENT",
    "GNEWS_DC_LEASE_DEAL",
    "GNEWS_DC_OPERATOR",
    "GNEWS_DC_SUPPLY_CHAIN",
)
DATE_TOKEN = re.compile(
    r"(?:^|\s)(?:when:\d+[dhmy]|after:\d{4}-\d{2}-\d{2}|before:\d{4}-\d{2}-\d{2})(?=\s|$)",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Google News 상용 데이터센터 메타데이터 기간 백필"
    )
    parser.add_argument("--from-date", help="시작일 YYYY-MM-DD (포함)")
    parser.add_argument("--to-date", help="종료일 YYYY-MM-DD (포함)")
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="명시적 날짜가 없을 때 오늘을 포함한 수집 일수",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=31,
        help="검색 구간 크기. Google News 결과 제한을 피하기 위해 기본 31일",
    )
    parser.add_argument(
        "--feed-code",
        action="append",
        dest="feed_codes",
        help="대상 피드 코드. 여러 번 지정 가능; 생략 시 상용시장 5개 피드",
    )
    parser.add_argument("--max-items", type=int, default=100)
    args = parser.parse_args()
    if bool(args.from_date) != bool(args.to_date):
        raise rss.CollectorError("--from-date와 --to-date를 함께 입력해야 합니다.")
    if args.days < 1 or args.days > 3660:
        raise rss.CollectorError("--days는 1~3660 사이여야 합니다.")
    if args.window_days < 1 or args.window_days > 93:
        raise rss.CollectorError("--window-days는 1~93 사이여야 합니다.")
    if args.max_items < 1 or args.max_items > 5000:
        raise rss.CollectorError("--max-items는 1~5000 사이여야 합니다.")
    return args


def resolve_range(args: argparse.Namespace, today: date | None = None) -> tuple[date, date]:
    current = today or datetime.now().astimezone().date()
    if args.from_date:
        start = date.fromisoformat(args.from_date)
        inclusive_end = date.fromisoformat(args.to_date)
    else:
        inclusive_end = current
        start = current - timedelta(days=args.days - 1)
    if start > inclusive_end:
        raise rss.CollectorError("수집 시작일은 종료일보다 늦을 수 없습니다.")
    return start, inclusive_end + timedelta(days=1)


def iter_windows(start: date, end_exclusive: date, size_days: int) -> Iterator[tuple[date, date]]:
    cursor = start
    while cursor < end_exclusive:
        window_end = min(cursor + timedelta(days=size_days), end_exclusive)
        yield cursor, window_end
        cursor = window_end


def dated_feed_url(feed_url: str, start: date, end_exclusive: date) -> str:
    parsed = urlsplit(feed_url)
    parameters = parse_qsl(parsed.query, keep_blank_values=True)
    output: list[tuple[str, str]] = []
    found_query = False
    for key, value in parameters:
        if key == "q":
            found_query = True
            cleaned = " ".join(DATE_TOKEN.sub(" ", value).split())
            value = f"{cleaned} after:{start.isoformat()} before:{end_exclusive.isoformat()}"
        output.append((key, value))
    if not found_query:
        raise rss.CollectorError("Google News 피드 URL에 q 검색어가 없습니다.")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(output), parsed.fragment))


def in_window(item: dict[str, Any], start: date, end_exclusive: date) -> bool:
    published = item.get("published_at")
    if published is None:
        return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    published_date = published.astimezone(timezone.utc).date()
    return start <= published_date < end_exclusive


def select_feeds(engine: Any, requested: list[str] | None) -> list[dict[str, Any]]:
    wanted = set(requested or DEFAULT_FEEDS)
    args = SimpleNamespace(source_code="GOOGLE_NEWS_DC", feed_code=None)
    feeds = [feed for feed in rss.load_feeds(engine, args) if feed["feed_code"] in wanted]
    missing = sorted(wanted - {feed["feed_code"] for feed in feeds})
    if missing:
        raise rss.CollectorError(f"실행 가능한 Google News 피드가 없습니다: {', '.join(missing)}")
    return feeds


def collect(
    engine: Any,
    feeds: list[dict[str, Any]],
    start: date,
    end_exclusive: date,
    window_days: int,
    max_items: int,
    raw_root: Path,
) -> rss.SourceResult:
    first = feeds[0]
    windows = list(iter_windows(start, end_exclusive, window_days))
    result = rss.SourceResult(str(first["source_code"]), str(first["source_name"]))
    run_id = rss.create_collection_run(
        engine, "BACKFILL", 1, job_name="GOOGLE_NEWS_HISTORY_BACKFILL"
    )
    source_run_id = rss.create_source_run(engine, run_id, first["source_id"])

    total_requests = len(feeds) * len(windows)
    request_number = 0
    for feed in feeds:
        feed_failed = False
        feed_items: list[dict[str, Any]] = []
        for window_start, window_end in windows:
            request_number += 1
            window_feed = {
                **feed,
                "feed_url": dated_feed_url(feed["feed_url"], window_start, window_end),
                "etag": None,
                "last_modified": None,
            }
            try:
                status, payload, _etag, _modified, _url = rss.fetch_feed(
                    window_feed, result.metrics
                )
                if status == 304:
                    items = []
                else:
                    parsed = rss.parse_feed(payload, max_items)
                    items = [item for item in parsed if in_window(item, window_start, window_end)]
                    result.counts.skipped += len(parsed) - len(items)
                    counts = rss.store_items(
                        engine,
                        feed,
                        items,
                        raw_root,
                        collection_kind="news_backfill",
                        collector_version=VERSION,
                        parser_name="google-news-rss-history",
                    )
                    result.counts.add(counts)
                    feed_items.extend(items)
                print(
                    f"[{request_number}/{total_requests}] {feed['feed_code']} "
                    f"{window_start.isoformat()}~{(window_end - timedelta(days=1)).isoformat()} "
                    f"확인 {len(items)}건"
                )
            except Exception as error:
                feed_failed = True
                result.errors.append(
                    f"{feed['feed_code']} {window_start.isoformat()}~{window_end.isoformat()}: {error}"
                )
                print(f"백필 구간 실패 - {result.errors[-1]}", file=sys.stderr)
            finally:
                if request_number < total_requests:
                    time.sleep(max(float(feed["request_interval_seconds"]), 1.0))

        if feed_failed:
            result.failed_feeds += 1
            rss.mark_feed_failed(engine, feed["feed_id"], rss.CollectorError("과거자료 일부 구간 실패"))
        else:
            result.successful_feeds += 1
            rss.mark_feed_success(engine, feed["feed_id"], None, None, feed_items)

    rss.finish_source_run(engine, source_run_id, result)
    rss.finish_collection_run(engine, run_id, [result])
    return result


def main() -> int:
    rss.load_env_file()
    engine = None
    try:
        args = parse_args()
        start, end_exclusive = resolve_range(args)
        engine = create_engine(rss.resolve_database_url(), pool_pre_ping=True)
        feeds = select_feeds(engine, args.feed_codes)
        result = collect(
            engine,
            feeds,
            start,
            end_exclusive,
            args.window_days,
            args.max_items,
            Path(__import__("os").getenv("RAW_DATA_DIR", "data/raw")),
        )
        print(
            f"백필 완료: {start.isoformat()}~{(end_exclusive - timedelta(days=1)).isoformat()}, "
            f"피드 {len(feeds)}개, 발견 {result.counts.found}, 신규 {result.counts.new}, "
            f"변경 {result.counts.updated}, 제외·중복 {result.counts.skipped}"
        )
        return 1 if result.failed_feeds else 0
    except Exception as error:
        print(f"Google News 백필 실패: {error}", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
