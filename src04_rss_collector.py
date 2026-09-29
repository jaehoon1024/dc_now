#!/usr/bin/env python3
"""Collect data-center-related metadata from approved RSS/Atom feeds.

The collector reads active feeds from ``source_feed`` and stores only minimum
metadata: title, canonical URL, publisher, and publication time.  It never
stores an article body, RSS description, image, or embedded media.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


VERSION = "src04-1.0.1"
USER_AGENT = "dc-platform-rss-collector/1.0 (+metadata-only)"
TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
}


class CollectorError(RuntimeError):
    """Raised for a controlled collector failure."""


@dataclass
class Metrics:
    request_count: int = 0
    downloaded_bytes: int = 0


@dataclass
class Counts:
    found: int = 0
    new: int = 0
    updated: int = 0
    skipped: int = 0

    def add(self, other: "Counts") -> None:
        self.found += other.found
        self.new += other.new
        self.updated += other.updated
        self.skipped += other.skipped


@dataclass
class SourceResult:
    source_code: str
    source_name: str
    metrics: Metrics = field(default_factory=Metrics)
    counts: Counts = field(default_factory=Counts)
    successful_feeds: int = 0
    failed_feeds: int = 0
    errors: list[str] = field(default_factory=list)


def load_env_file(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE pairs without overwriting shell variables."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_database_url() -> str:
    explicit_url = os.getenv("DATABASE_URL", "").strip()
    if explicit_url:
        return explicit_url

    password = os.getenv("DC_DB_PASSWORD", "").strip()
    if not password:
        raise CollectorError(
            "DC_DB_PASSWORD가 없습니다. 기존 DB 비밀번호 환경변수를 확인하세요."
        )
    return URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DC_DB_USER", "dc_app"),
        password=password,
        host=os.getenv("DC_DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DC_DB_PORT", "5432")),
        database=os.getenv("DC_DB_NAME", "dc_platform"),
    ).render_as_string(hide_password=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="승인된 RSS에서 데이터센터 관련 최소 메타데이터 수집"
    )
    parser.add_argument(
        "--source-code",
        help="특정 출처만 실행 (예: MSIT_PRESS 또는 ETNEWS)",
    )
    parser.add_argument(
        "--feed-code",
        help="특정 피드만 실행 (예: ETNEWS_AI)",
    )
    parser.add_argument(
        "--trigger",
        choices=("MANUAL", "SCHEDULED", "RETRY", "BACKFILL"),
        default="MANUAL",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=int(os.getenv("RSS_MAX_ITEMS_PER_FEED", "500")),
        help="피드당 최대 처리 항목 수",
    )
    args = parser.parse_args()
    if args.max_items < 1 or args.max_items > 5000:
        raise CollectorError("--max-items는 1~5000 사이여야 합니다.")
    return args


def load_feeds(engine: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    filters = []
    parameters: dict[str, Any] = {}
    if args.source_code:
        filters.append("sr.source_code = :source_code")
        parameters["source_code"] = args.source_code
    if args.feed_code:
        filters.append("sf.feed_code = :feed_code")
        parameters["feed_code"] = args.feed_code
    filter_sql = ""
    if filters:
        filter_sql = " AND " + " AND ".join(filters)

    with engine.begin() as connection:
        rows = connection.execute(
            text(
                """
                SELECT
                    sf.feed_id,
                    sf.source_id,
                    sf.feed_code,
                    sf.feed_name,
                    sf.feed_url,
                    sf.feed_format,
                    sf.filter_mode,
                    sf.filter_keywords,
                    sf.storage_policy,
                    sf.request_interval_seconds,
                    sf.etag,
                    sf.last_modified,
                    sr.source_code,
                    sr.source_name,
                    sr.default_source_grade
                FROM source_feed sf
                JOIN source_registry sr ON sr.source_id = sf.source_id
                WHERE sf.active = true
                  AND sr.active = true
                  AND sr.terms_review_status IN ('ALLOWED', 'LIMITED')
                  AND sr.collection_policy = 'METADATA_ONLY'
                  AND sf.storage_policy = 'METADATA_ONLY'
                """
                + filter_sql
                + " ORDER BY sr.source_code, sf.feed_code"
            ),
            parameters,
        ).mappings().all()
    return [dict(row) for row in rows]


def create_collection_run(
    engine: Any,
    trigger_type: str,
    total_source_count: int,
) -> Any:
    with engine.begin() as connection:
        return connection.execute(
            text(
                """
                INSERT INTO collection_run (
                    job_name,
                    trigger_type,
                    requested_by,
                    started_at,
                    run_status,
                    total_source_count,
                    host_name,
                    application_version
                ) VALUES (
                    'RSS_DAILY',
                    :trigger_type,
                    :requested_by,
                    CURRENT_TIMESTAMP,
                    'RUNNING',
                    :total_source_count,
                    :host_name,
                    :version
                )
                RETURNING collection_run_id
                """
            ),
            {
                "trigger_type": trigger_type,
                "requested_by": os.getenv("USER", "dc-platform"),
                "total_source_count": total_source_count,
                "host_name": socket.gethostname(),
                "version": VERSION,
            },
        ).scalar_one()


def create_source_run(engine: Any, run_id: Any, source_id: Any) -> Any:
    with engine.begin() as connection:
        return connection.execute(
            text(
                """
                INSERT INTO collection_source_run (
                    collection_run_id,
                    source_id,
                    started_at,
                    run_status
                ) VALUES (
                    :run_id,
                    :source_id,
                    CURRENT_TIMESTAMP,
                    'RUNNING'
                )
                RETURNING collection_source_run_id
                """
            ),
            {"run_id": run_id, "source_id": source_id},
        ).scalar_one()


def fetch_feed(
    feed: dict[str, Any],
    metrics: Metrics,
) -> tuple[int, bytes, str | None, str | None, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
    }
    if feed.get("etag"):
        headers["If-None-Match"] = str(feed["etag"])
    if feed.get("last_modified"):
        headers["If-Modified-Since"] = str(feed["last_modified"])

    timeout = float(os.getenv("RSS_HTTP_TIMEOUT_SECONDS", "30"))
    max_bytes = int(os.getenv("RSS_MAX_DOWNLOAD_BYTES", "5000000"))
    request = Request(str(feed["feed_url"]), headers=headers)
    metrics.request_count += 1
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise CollectorError(
                    f"{feed['feed_code']} 응답이 제한({max_bytes} bytes)을 초과했습니다."
                )
            metrics.downloaded_bytes += len(payload)
            return (
                int(response.status),
                payload,
                response.headers.get("ETag"),
                response.headers.get("Last-Modified"),
                response.geturl(),
            )
    except HTTPError as error:
        if error.code == 304:
            return 304, b"", feed.get("etag"), feed.get("last_modified"), str(feed["feed_url"])
        raise CollectorError(
            f"{feed['feed_code']} HTTP 오류: {error.code} {error.reason}"
        ) from error


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def first_text(element: ET.Element, names: tuple[str, ...]) -> str:
    wanted = set(names)
    for child in element:
        if local_name(child.tag) in wanted and child.text:
            value = " ".join(child.text.split())
            if value:
                return value
    return ""


def item_link(element: ET.Element) -> str:
    fallback = ""
    for child in element:
        if local_name(child.tag) != "link":
            continue
        href = (child.attrib.get("href") or "").strip()
        relation = (child.attrib.get("rel") or "alternate").lower()
        if href and relation == "alternate":
            return href
        if href and not fallback:
            fallback = href
        if child.text and child.text.strip() and not fallback:
            fallback = child.text.strip()
    return fallback


def parse_datetime(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError, OverflowError):
        pass

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def canonicalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return ""
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in TRACKING_PARAMETERS
    ]
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "/",
            urlencode(query, doseq=True),
            "",
        )
    )


def parse_feed(payload: bytes, max_items: int) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise CollectorError(f"RSS XML 해석 실패: {error}") from error

    entry_names = {"item", "entry"}
    entries = [element for element in root.iter() if local_name(element.tag) in entry_names]
    parsed_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries[:max_items]:
        title = first_text(entry, ("title",))
        link = canonicalize_url(item_link(entry))
        guid = first_text(entry, ("guid", "id"))
        published_raw = first_text(
            entry,
            ("pubdate", "published", "updated", "date"),
        )
        identity = link or guid
        if not title or not link or not identity or identity in seen:
            continue
        seen.add(identity)
        parsed_items.append(
            {
                "title": title,
                "canonical_url": link,
                "guid": guid,
                "published_raw": published_raw,
                "published_at": parse_datetime(published_raw),
            }
        )
    return parsed_items


def relevance_reason(
    title: str,
    filter_mode: str,
    keywords: list[str],
) -> str | None:
    if filter_mode == "ALL":
        return "ALL"
    upper_title = title.upper()
    for keyword in keywords:
        if str(keyword).upper() in upper_title:
            return f"KEYWORD:{keyword}"
    if filter_mode == "MANUAL_REVIEW":
        return "MANUAL_REVIEW"
    return None


def external_document_id(
    source_code: str,
    canonical_url: str,
    prefix: str = "rss",
) -> str:
    digest = hashlib.sha256(
        f"{source_code}|{canonical_url}".encode("utf-8")
    ).hexdigest()
    return f"{prefix}:{digest}"


def save_evidence_json(
    raw_root: Path,
    feed: dict[str, Any],
    item: dict[str, Any],
    reason: str,
    external_id: str,
    *,
    collection_kind: str = "rss",
    collector_version: str = VERSION,
) -> tuple[Path, str]:
    published_at = item.get("published_at") or datetime.now(timezone.utc)
    target_dir = (
        raw_root
        / collection_kind
        / str(feed["source_code"]).lower()
        / published_at.strftime("%Y/%m/%d")
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    external_key = external_id.split(":", 1)[-1]
    target_path = target_dir / f"{external_key}.json"
    evidence = {
        "collector_version": collector_version,
        "storage_policy": "METADATA_ONLY",
        "source_code": feed["source_code"],
        "feed_code": feed["feed_code"],
        "relevance_reason": reason,
        "external_document_id": external_id,
        "title": item["title"],
        "canonical_url": item["canonical_url"],
        "publisher": feed["source_name"],
        "published_at": (
            item["published_at"].isoformat() if item.get("published_at") else None
        ),
    }
    canonical_bytes = json.dumps(
        evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(canonical_bytes).hexdigest()
    target_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target_path.resolve(), digest


def store_items(
    engine: Any,
    feed: dict[str, Any],
    items: list[dict[str, Any]],
    raw_root: Path,
    *,
    collection_kind: str = "rss",
    collector_version: str = VERSION,
    parser_name: str = "rss-metadata",
    external_id_prefix: str = "rss",
) -> Counts:
    counts = Counts(found=len(items))
    keywords = feed.get("filter_keywords") or []
    if isinstance(keywords, str):
        keywords = json.loads(keywords)

    with engine.begin() as connection:
        for item in items:
            reason = relevance_reason(
                item["title"],
                str(feed["filter_mode"]),
                list(keywords),
            )
            if reason is None:
                counts.skipped += 1
                continue

            external_id = external_document_id(
                str(feed["source_code"]),
                item["canonical_url"],
                external_id_prefix,
            )
            raw_path, digest = save_evidence_json(
                raw_root,
                feed,
                item,
                reason,
                external_id,
                collection_kind=collection_kind,
                collector_version=collector_version,
            )
            existing = connection.execute(
                text(
                    """
                    SELECT document_id
                    FROM evidence_document
                    WHERE source_id = :source_id
                      AND external_document_id = :external_document_id
                    LIMIT 1
                    """
                ),
                {
                    "source_id": feed["source_id"],
                    "external_document_id": external_id,
                },
            ).mappings().first()

            is_new = existing is None
            if is_new:
                document_id = connection.execute(
                    text(
                        """
                        INSERT INTO evidence_document (
                            source_id,
                            canonical_url,
                            external_document_id,
                            title,
                            document_type,
                            publisher,
                            published_at,
                            language_code,
                            source_grade,
                            access_scope,
                            record_status
                        ) VALUES (
                            :source_id,
                            :canonical_url,
                            :external_document_id,
                            :title,
                            'NEWS',
                            :publisher,
                            :published_at,
                            'ko',
                            :source_grade,
                            'PUBLIC',
                            'ACTIVE'
                        )
                        RETURNING document_id
                        """
                    ),
                    {
                        "source_id": feed["source_id"],
                        "canonical_url": item["canonical_url"],
                        "external_document_id": external_id,
                        "title": item["title"],
                        "publisher": feed["source_name"],
                        "published_at": item.get("published_at"),
                        "source_grade": feed["default_source_grade"],
                    },
                ).scalar_one()
            else:
                document_id = existing["document_id"]

            hash_exists = connection.execute(
                text(
                    """
                    SELECT 1
                    FROM evidence_document_version
                    WHERE document_id = :document_id
                      AND content_hash_sha256 = :digest
                    LIMIT 1
                    """
                ),
                {"document_id": document_id, "digest": digest},
            ).first()
            if hash_exists:
                counts.skipped += 1
                continue

            version_no = connection.execute(
                text(
                    """
                    SELECT COALESCE(MAX(version_no), 0) + 1
                    FROM evidence_document_version
                    WHERE document_id = :document_id
                    """
                ),
                {"document_id": document_id},
            ).scalar_one()
            connection.execute(
                text(
                    """
                    UPDATE evidence_document_version
                    SET is_current = false
                    WHERE document_id = :document_id AND is_current = true
                    """
                ),
                {"document_id": document_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO evidence_document_version (
                        document_id,
                        version_no,
                        http_status,
                        mime_type,
                        content_hash_sha256,
                        raw_storage_path,
                        parser_name,
                        parser_version,
                        extraction_status,
                        is_current
                    ) VALUES (
                        :document_id,
                        :version_no,
                        200,
                        'application/json',
                        :digest,
                        :raw_path,
                        :parser_name,
                        :parser_version,
                        'SUCCESS',
                        true
                    )
                    """
                ),
                {
                    "document_id": document_id,
                    "version_no": version_no,
                    "digest": digest,
                    "raw_path": str(raw_path),
                    "parser_name": parser_name,
                    "parser_version": collector_version,
                },
            )
            connection.execute(
                text(
                    """
                    UPDATE evidence_document
                    SET canonical_url = :canonical_url,
                        title = :title,
                        publisher = :publisher,
                        published_at = :published_at,
                        record_status = 'ACTIVE'
                    WHERE document_id = :document_id
                    """
                ),
                {
                    "document_id": document_id,
                    "canonical_url": item["canonical_url"],
                    "title": item["title"],
                    "publisher": feed["source_name"],
                    "published_at": item.get("published_at"),
                },
            )
            if is_new:
                counts.new += 1
            else:
                counts.updated += 1
    return counts


def mark_feed_success(
    engine: Any,
    feed_id: Any,
    etag: str | None,
    last_modified: str | None,
    items: list[dict[str, Any]],
) -> None:
    published_values = [
        item["published_at"] for item in items if item.get("published_at") is not None
    ]
    latest_published = max(published_values) if published_values else None
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE source_feed
                SET etag = COALESCE(:etag, etag),
                    last_modified = COALESCE(:last_modified, last_modified),
                    last_polled_at = CURRENT_TIMESTAMP,
                    last_success_at = CURRENT_TIMESTAMP,
                    last_item_published_at = CASE
                        WHEN CAST(:latest_published AS timestamptz) IS NULL THEN last_item_published_at
                        WHEN last_item_published_at IS NULL THEN :latest_published
                        ELSE GREATEST(last_item_published_at, :latest_published)
                    END,
                    consecutive_failure_count = 0,
                    last_error = NULL
                WHERE feed_id = :feed_id
                """
            ),
            {
                "feed_id": feed_id,
                "etag": etag,
                "last_modified": last_modified,
                "latest_published": latest_published,
            },
        )


def mark_feed_failed(engine: Any, feed_id: Any, error: Exception) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE source_feed
                SET last_polled_at = CURRENT_TIMESTAMP,
                    consecutive_failure_count = consecutive_failure_count + 1,
                    last_error = :last_error
                WHERE feed_id = :feed_id
                """
            ),
            {"feed_id": feed_id, "last_error": str(error)[:2000]},
        )


def finish_source_run(
    engine: Any,
    source_run_id: Any,
    result: SourceResult,
) -> None:
    failed = result.failed_feeds > 0
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE collection_source_run
                SET finished_at = CURRENT_TIMESTAMP,
                    run_status = :run_status,
                    request_count = :request_count,
                    found_item_count = :found,
                    new_item_count = :new,
                    updated_item_count = :updated,
                    skipped_item_count = :skipped,
                    downloaded_bytes = :downloaded_bytes,
                    error_code = :error_code,
                    error_message = :error_message
                WHERE collection_source_run_id = :source_run_id
                """
            ),
            {
                "source_run_id": source_run_id,
                "run_status": "FAILED" if failed else "SUCCESS",
                "request_count": result.metrics.request_count,
                "found": result.counts.found,
                "new": result.counts.new,
                "updated": result.counts.updated,
                "skipped": result.counts.skipped,
                "downloaded_bytes": result.metrics.downloaded_bytes,
                "error_code": "RSS_FEED_FAILURE" if failed else None,
                "error_message": " | ".join(result.errors)[:2000] if failed else None,
            },
        )


def finish_collection_run(
    engine: Any,
    run_id: Any,
    results: list[SourceResult],
) -> None:
    success_count = sum(1 for result in results if result.failed_feeds == 0)
    failed_count = len(results) - success_count
    if failed_count == 0:
        status = "SUCCESS"
    elif success_count == 0:
        status = "FAILED"
    else:
        status = "PARTIAL"
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE collection_run
                SET finished_at = CURRENT_TIMESTAMP,
                    run_status = :run_status,
                    success_source_count = :success_count,
                    failed_source_count = :failed_count,
                    new_document_count = :new_count,
                    updated_document_count = :updated_count,
                    error_summary = :error_summary
                WHERE collection_run_id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "run_status": status,
                "success_count": success_count,
                "failed_count": failed_count,
                "new_count": sum(result.counts.new for result in results),
                "updated_count": sum(result.counts.updated for result in results),
                "error_summary": (
                    " | ".join(
                        error
                        for result in results
                        for error in result.errors
                    )[:4000]
                    if failed_count
                    else None
                ),
            },
        )


def group_feeds(feeds: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_source_id: Any = None
    for feed in feeds:
        if current and feed["source_id"] != current_source_id:
            groups.append(current)
            current = []
        current.append(feed)
        current_source_id = feed["source_id"]
    if current:
        groups.append(current)
    return groups


def collect_source(
    engine: Any,
    run_id: Any,
    feeds: list[dict[str, Any]],
    raw_root: Path,
    max_items: int,
) -> SourceResult:
    first_feed = feeds[0]
    result = SourceResult(
        source_code=str(first_feed["source_code"]),
        source_name=str(first_feed["source_name"]),
    )
    source_run_id = create_source_run(engine, run_id, first_feed["source_id"])

    for feed_index, feed in enumerate(feeds):
        try:
            status, payload, etag, last_modified, _final_url = fetch_feed(
                feed,
                result.metrics,
            )
            if status == 304:
                mark_feed_success(engine, feed["feed_id"], etag, last_modified, [])
                result.successful_feeds += 1
            else:
                items = parse_feed(payload, max_items)
                counts = store_items(engine, feed, items, raw_root)
                result.counts.add(counts)
                mark_feed_success(
                    engine,
                    feed["feed_id"],
                    etag,
                    last_modified,
                    items,
                )
                result.successful_feeds += 1
        except Exception as error:
            result.failed_feeds += 1
            message = f"{feed['feed_code']}: {error}"
            result.errors.append(message)
            mark_feed_failed(engine, feed["feed_id"], error)
            print(f"피드 실패 - {message}", file=sys.stderr)
        finally:
            if feed_index < len(feeds) - 1:
                time.sleep(max(float(feed["request_interval_seconds"]), 1.0))

    finish_source_run(engine, source_run_id, result)
    return result


def main() -> int:
    load_env_file()
    engine = None
    run_id = None
    results: list[SourceResult] = []
    try:
        args = parse_args()
        engine = create_engine(resolve_database_url(), pool_pre_ping=True)
        feeds = load_feeds(engine, args)
        if not feeds:
            raise CollectorError("실행 가능한 RSS 피드가 없습니다. 0010 마이그레이션을 확인하세요.")

        feed_groups = group_feeds(feeds)
        run_id = create_collection_run(engine, args.trigger, len(feed_groups))
        raw_root = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
        for source_feeds in feed_groups:
            results.append(
                collect_source(
                    engine,
                    run_id,
                    source_feeds,
                    raw_root,
                    args.max_items,
                )
            )
        finish_collection_run(engine, run_id, results)

        print(f"RSS 출처 {len(results)}개 / 피드 {len(feeds)}개 처리")
        for result in results:
            print(
                f"- {result.source_code}: 성공 피드 {result.successful_feeds}, "
                f"실패 피드 {result.failed_feeds}, 발견 {result.counts.found}, "
                f"신규 {result.counts.new}, 변경 {result.counts.updated}, "
                f"제외·중복 {result.counts.skipped}"
            )
        return 1 if any(result.failed_feeds for result in results) else 0
    except Exception as error:
        if engine is not None and run_id is not None and not results:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        UPDATE collection_run
                        SET finished_at = CURRENT_TIMESTAMP,
                            run_status = 'FAILED',
                            failed_source_count = total_source_count,
                            error_summary = :error_summary
                        WHERE collection_run_id = :run_id
                        """
                    ),
                    {"run_id": run_id, "error_summary": str(error)[:4000]},
                )
        print(f"RSS 수집 실패: {error}", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
