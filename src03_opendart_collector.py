#!/usr/bin/env python3
"""OpenDART metadata collector for the data-center intelligence database.

This collector uses only the official OpenDART API. It stores filing metadata
and a local JSON evidence file; it does not scrape or copy web page content.
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
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


VERSION = "src03-1.0.1"
KST = timezone(timedelta(hours=9))
API_BASE = "https://opendart.fss.or.kr/api"
VIEW_BASE = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="

# DBO 관점에서 우선 확인할 국내 운영사·클라우드·IT서비스 기업입니다.
# 상장사는 종목코드로, 비상장사는 정규화한 법인명으로 DART 고유번호를 찾습니다.
DEFAULT_TARGETS = (
    ("LG유플러스", "032640"),
    ("LG씨엔에스", "064400"),
    ("케이티", "030200"),
    ("SK텔레콤", "017670"),
    ("에스케이브로드밴드", ""),
    ("삼성에스디에스", "018260"),
    ("NAVER", "035420"),
    ("NHN", "181710"),
    ("케이아이엔엑스", "093320"),
    ("가비아", "079940"),
    ("롯데이노베이트", "286940"),
)

DIRECT_KEYWORDS = (
    "데이터센터",
    "데이터 센터",
    "IDC",
    "AIDC",
    "클라우드센터",
    "AI센터",
    "AI 센터",
    "전산센터",
)

# 제목만으로 데이터센터 관련 여부를 완전히 판단할 수 없으므로,
# 설비투자·부동산·정기보고서도 후보 증거로 수집합니다.
CANDIDATE_REPORT_KEYWORDS = (
    "사업보고서",
    "반기보고서",
    "분기보고서",
    "주요사항보고서",
    "유형자산",
    "영업양수",
    "영업양도",
    "자산양수",
    "자산양도",
    "타법인주식",
    "신규시설투자",
    "시설투자",
    "투자판단",
    "기업설명회",
    "증권신고서",
)


class CollectorError(RuntimeError):
    """Raised for a controlled collection failure."""


class Metrics:
    def __init__(self) -> None:
        self.request_count = 0
        self.downloaded_bytes = 0


def load_env_file(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE entries without overwriting shell variables."""
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
    """Reuse the same DC_DB_* settings used by the Alembic environment."""
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


def api_get_bytes(
    endpoint: str,
    params: dict[str, Any],
    metrics: Metrics,
    request_interval: float,
) -> bytes:
    url = f"{API_BASE}/{endpoint}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "User-Agent": "dc-platform-opendart-collector/1.0",
            "Accept": "application/json, application/zip, application/xml",
        },
    )
    with urlopen(request, timeout=40) as response:
        payload = response.read()
    metrics.request_count += 1
    metrics.downloaded_bytes += len(payload)
    time.sleep(max(request_interval, 1.0))
    return payload


def normalize_corp_name(value: str) -> str:
    normalized = value.upper().strip()
    normalized = re.sub(r"\(주\)|㈜|주식회사|CO\.?[,]?\s*LTD\.?", "", normalized)
    return re.sub(r"[^0-9A-Z가-힣]", "", normalized)


def parse_targets(value: str | None) -> tuple[tuple[str, str], ...]:
    if not value:
        return DEFAULT_TARGETS
    targets: list[tuple[str, str]] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if ":" in token:
            name, stock_code = token.split(":", 1)
        else:
            name, stock_code = token, ""
        targets.append((name.strip(), stock_code.strip()))
    if not targets:
        raise CollectorError("OPENDART_TARGETS에 유효한 기업이 없습니다.")
    return tuple(targets)


def load_corp_codes(
    api_key: str,
    targets: tuple[tuple[str, str], ...],
    cache_path: Path,
    metrics: Metrics,
    request_interval: float,
) -> tuple[list[dict[str, str]], list[str]]:
    if cache_path.exists():
        age = datetime.now().timestamp() - cache_path.stat().st_mtime
        if age < 7 * 24 * 60 * 60:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_targets = cached.get("targets", [])
            cached_keys = {
                (item.get("requested_name", ""), item.get("stock_code", ""))
                for item in cached_targets
            }
            if all(target in cached_keys for target in targets):
                return cached_targets, cached.get("missing_targets", [])

    payload = api_get_bytes(
        "corpCode.xml",
        {"crtfc_key": api_key},
        metrics,
        request_interval,
    )
    try:
        with ZipFile(BytesIO(payload)) as archive:
            xml_name = next(
                name for name in archive.namelist() if name.upper().endswith(".XML")
            )
            root = ET.fromstring(archive.read(xml_name))
    except (BadZipFile, StopIteration, ET.ParseError) as exc:
        message = payload[:300].decode("utf-8", errors="replace")
        raise CollectorError(f"DART 고유번호 파일 해석 실패: {message}") from exc

    by_stock: dict[str, dict[str, str]] = {}
    by_name: dict[str, dict[str, str]] = {}
    for element in root.findall("list"):
        item = {
            "corp_code": (element.findtext("corp_code") or "").strip(),
            "corp_name": (element.findtext("corp_name") or "").strip(),
            "stock_code": (element.findtext("stock_code") or "").strip(),
            "modify_date": (element.findtext("modify_date") or "").strip(),
        }
        if item["stock_code"]:
            by_stock[item["stock_code"]] = item
        by_name[normalize_corp_name(item["corp_name"])] = item

    resolved: list[dict[str, str]] = []
    missing: list[str] = []
    for requested_name, stock_code in targets:
        match = by_stock.get(stock_code) if stock_code else None
        if match is None:
            match = by_name.get(normalize_corp_name(requested_name))
        if match is None:
            missing.append(requested_name)
            continue
        resolved.append(
            {
                "requested_name": requested_name,
                "corp_code": match["corp_code"],
                "corp_name": match["corp_name"],
                "stock_code": match["stock_code"],
                "modify_date": match["modify_date"],
            }
        )

    if not resolved:
        raise CollectorError("대상 기업의 DART 고유번호를 하나도 찾지 못했습니다.")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(KST).isoformat(),
                "targets": resolved,
                "missing_targets": missing,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return resolved, missing


def fetch_filings(
    api_key: str,
    companies: list[dict[str, str]],
    start_date: date,
    end_date: date,
    metrics: Metrics,
    request_interval: float,
) -> list[dict[str, Any]]:
    filings_by_id: dict[str, dict[str, Any]] = {}
    for company in companies:
        page_no = 1
        while True:
            payload = api_get_bytes(
                "list.json",
                {
                    "crtfc_key": api_key,
                    "corp_code": company["corp_code"],
                    "bgn_de": start_date.strftime("%Y%m%d"),
                    "end_de": end_date.strftime("%Y%m%d"),
                    "page_no": page_no,
                    "page_count": 100,
                    "last_reprt_at": "N",
                },
                metrics,
                request_interval,
            )
            result = json.loads(payload.decode("utf-8"))
            status = result.get("status")
            if status == "013":
                break
            if status != "000":
                raise CollectorError(
                    f"OpenDART 응답 오류 {status}: {result.get('message', '내용 없음')}"
                )
            for item in result.get("list", []):
                item["target_name"] = company["requested_name"]
                filings_by_id[item["rcept_no"]] = item
            total_page = int(result.get("total_page", 1))
            if page_no >= total_page:
                break
            page_no += 1
    return list(filings_by_id.values())


def relevance_reason(title: str) -> str | None:
    upper = title.upper()
    for keyword in DIRECT_KEYWORDS:
        if keyword.upper() in upper:
            return f"DIRECT:{keyword}"
    for keyword in CANDIDATE_REPORT_KEYWORDS:
        if keyword.upper() in upper:
            return f"CANDIDATE:{keyword}"
    return None


def parse_filing_date(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y%m%d")
    return parsed.replace(tzinfo=KST)


def save_evidence_json(
    raw_root: Path,
    item: dict[str, Any],
    reason: str,
) -> tuple[Path, str]:
    receipt_date = datetime.strptime(item["rcept_dt"], "%Y%m%d")
    target_dir = raw_root / "opendart" / receipt_date.strftime("%Y/%m/%d")
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{item['rcept_no']}.json"
    evidence = {
        "collector_version": VERSION,
        "relevance_reason": reason,
        "source": "OPENDART",
        "filing": item,
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


def create_run(engine: Any, source_id: Any, trigger_type: str) -> tuple[Any, Any]:
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                """
                INSERT INTO collection_run (
                    job_name, trigger_type, requested_by, started_at, run_status,
                    total_source_count, host_name, application_version
                ) VALUES (
                    'OPENDART_DAILY', :trigger_type, :requested_by,
                    CURRENT_TIMESTAMP, 'RUNNING', 1, :host_name, :version
                )
                RETURNING collection_run_id
                """
            ),
            {
                "trigger_type": trigger_type,
                "requested_by": os.getenv("USER", "dc-platform"),
                "host_name": socket.gethostname(),
                "version": VERSION,
            },
        ).scalar_one()
        source_run_id = connection.execute(
            text(
                """
                INSERT INTO collection_source_run (
                    collection_run_id, source_id, started_at, run_status
                ) VALUES (
                    :run_id, :source_id, CURRENT_TIMESTAMP, 'RUNNING'
                )
                RETURNING collection_source_run_id
                """
            ),
            {"run_id": run_id, "source_id": source_id},
        ).scalar_one()
    return run_id, source_run_id


def store_filings(
    engine: Any,
    source_id: Any,
    source_run_id: Any,
    run_id: Any,
    filings: list[dict[str, Any]],
    raw_root: Path,
    metrics: Metrics,
) -> dict[str, int]:
    relevant: list[tuple[dict[str, Any], str]] = []
    for item in filings:
        reason = relevance_reason(item.get("report_nm", ""))
        if reason:
            relevant.append((item, reason))

    counts = {"found": len(filings), "new": 0, "updated": 0, "skipped": 0}
    with engine.begin() as connection:
        for item, reason in relevant:
            receipt_no = item["rcept_no"]
            raw_path, digest = save_evidence_json(raw_root, item, reason)
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
                {"source_id": source_id, "external_document_id": receipt_no},
            ).mappings().first()

            is_new = existing is None
            if is_new:
                document_id = connection.execute(
                    text(
                        """
                        INSERT INTO evidence_document (
                            source_id, canonical_url, external_document_id, title,
                            document_type, publisher, published_at, language_code,
                            source_grade, access_scope, record_status
                        ) VALUES (
                            :source_id, :canonical_url, :external_document_id, :title,
                            'DISCLOSURE', :publisher, :published_at, 'ko',
                            'A', 'PUBLIC', 'ACTIVE'
                        )
                        RETURNING document_id
                        """
                    ),
                    {
                        "source_id": source_id,
                        "canonical_url": VIEW_BASE + receipt_no,
                        "external_document_id": receipt_no,
                        "title": item.get("report_nm") or "제목 없음",
                        "publisher": item.get("corp_name"),
                        "published_at": parse_filing_date(item["rcept_dt"]),
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
                    """
                ),
                {"document_id": document_id, "digest": digest},
            ).first()
            if hash_exists:
                counts["skipped"] += 1
                continue

            next_version = connection.execute(
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
                        document_id, version_no, http_status, mime_type,
                        content_hash_sha256, raw_storage_path, parser_name,
                        parser_version, extraction_status, is_current
                    ) VALUES (
                        :document_id, :version_no, 200, 'application/json',
                        :digest, :raw_path, 'opendart-metadata',
                        :parser_version, 'SUCCESS', true
                    )
                    """
                ),
                {
                    "document_id": document_id,
                    "version_no": next_version,
                    "digest": digest,
                    "raw_path": str(raw_path),
                    "parser_version": VERSION,
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
                    "canonical_url": VIEW_BASE + receipt_no,
                    "title": item.get("report_nm") or "제목 없음",
                    "publisher": item.get("corp_name"),
                    "published_at": parse_filing_date(item["rcept_dt"]),
                },
            )
            if is_new:
                counts["new"] += 1
            else:
                counts["updated"] += 1

        counts["skipped"] += counts["found"] - len(relevant)
        connection.execute(
            text(
                """
                UPDATE collection_source_run
                SET finished_at = CURRENT_TIMESTAMP,
                    run_status = 'SUCCESS',
                    request_count = :request_count,
                    found_item_count = :found,
                    new_item_count = :new,
                    updated_item_count = :updated,
                    skipped_item_count = :skipped,
                    downloaded_bytes = :downloaded_bytes
                WHERE collection_source_run_id = :source_run_id
                """
            ),
            {
                "source_run_id": source_run_id,
                "request_count": metrics.request_count,
                "found": counts["found"],
                "new": counts["new"],
                "updated": counts["updated"],
                "skipped": counts["skipped"],
                "downloaded_bytes": metrics.downloaded_bytes,
            },
        )
        connection.execute(
            text(
                """
                UPDATE collection_run
                SET finished_at = CURRENT_TIMESTAMP,
                    run_status = 'SUCCESS',
                    success_source_count = 1,
                    new_document_count = :new,
                    updated_document_count = :updated
                WHERE collection_run_id = :run_id
                """
            ),
            {"run_id": run_id, "new": counts["new"], "updated": counts["updated"]},
        )
    return counts


def mark_failed(
    engine: Any,
    run_id: Any | None,
    source_run_id: Any | None,
    metrics: Metrics,
    error: Exception,
) -> None:
    message = str(error)[:2000]
    with engine.begin() as connection:
        if source_run_id is not None:
            connection.execute(
                text(
                    """
                    UPDATE collection_source_run
                    SET finished_at = CURRENT_TIMESTAMP,
                        run_status = 'FAILED',
                        request_count = :request_count,
                        downloaded_bytes = :downloaded_bytes,
                        error_code = :error_code,
                        error_message = :error_message
                    WHERE collection_source_run_id = :source_run_id
                    """
                ),
                {
                    "source_run_id": source_run_id,
                    "request_count": metrics.request_count,
                    "downloaded_bytes": metrics.downloaded_bytes,
                    "error_code": type(error).__name__,
                    "error_message": message,
                },
            )
        if run_id is not None:
            connection.execute(
                text(
                    """
                    UPDATE collection_run
                    SET finished_at = CURRENT_TIMESTAMP,
                        run_status = 'FAILED',
                        failed_source_count = 1,
                        error_summary = :error_message
                    WHERE collection_run_id = :run_id
                    """
                ),
                {"run_id": run_id, "error_message": message},
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OpenDART 데이터센터 관련 공시 메타데이터 수집"
    )
    parser.add_argument("--days", type=int, default=2, help="오늘을 포함한 수집 일수")
    parser.add_argument("--from-date", help="수집 시작일 YYYY-MM-DD")
    parser.add_argument("--to-date", help="수집 종료일 YYYY-MM-DD")
    parser.add_argument(
        "--trigger",
        choices=("MANUAL", "SCHEDULED", "RETRY", "BACKFILL"),
        default="MANUAL",
    )
    return parser.parse_args()


def resolve_dates(args: argparse.Namespace) -> tuple[date, date]:
    if args.from_date or args.to_date:
        if not args.from_date or not args.to_date:
            raise CollectorError("--from-date와 --to-date를 함께 입력해야 합니다.")
        start = date.fromisoformat(args.from_date)
        end = date.fromisoformat(args.to_date)
    else:
        if args.days < 1 or args.days > 366:
            raise CollectorError("--days는 1~366 사이여야 합니다.")
        end = datetime.now(KST).date()
        start = end - timedelta(days=args.days - 1)
    if start > end:
        raise CollectorError("시작일이 종료일보다 늦습니다.")
    return start, end


def main() -> int:
    load_env_file()
    args = parse_args()
    metrics = Metrics()
    run_id = None
    source_run_id = None
    engine = None

    try:
        database_url = resolve_database_url()
        api_key = os.getenv("OPENDART_API_KEY", "").strip()
        if len(api_key) != 40:
            raise CollectorError(
                "OPENDART_API_KEY가 없거나 40자 형식이 아닙니다. 인증키를 .env에 등록하세요."
            )

        start_date, end_date = resolve_dates(args)
        raw_root = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
        cache_path = Path("data/cache/opendart_corp_code_targets.json")
        request_interval = float(os.getenv("OPENDART_REQUEST_INTERVAL_SECONDS", "1"))
        targets = parse_targets(os.getenv("OPENDART_TARGETS"))

        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.begin() as connection:
            source = connection.execute(
                text(
                    """
                    SELECT source_id, active, terms_review_status, collection_policy
                    FROM source_registry
                    WHERE source_code = 'OPENDART'
                    """
                )
            ).mappings().first()
        if source is None:
            raise CollectorError("source_registry에 OPENDART가 없습니다.")
        if not source["active"]:
            raise CollectorError("OPENDART 출처가 비활성화되어 있습니다.")
        if source["terms_review_status"] not in ("ALLOWED", "LIMITED"):
            raise CollectorError("OPENDART 이용조건 승인이 완료되지 않았습니다.")
        if source["collection_policy"] != "OFFICIAL_API":
            raise CollectorError("OPENDART 수집 정책이 OFFICIAL_API가 아닙니다.")

        run_id, source_run_id = create_run(engine, source["source_id"], args.trigger)
        companies, missing = load_corp_codes(
            api_key,
            targets,
            cache_path,
            metrics,
            request_interval,
        )
        filings = fetch_filings(
            api_key,
            companies,
            start_date,
            end_date,
            metrics,
            request_interval,
        )
        counts = store_filings(
            engine,
            source["source_id"],
            source_run_id,
            run_id,
            filings,
            raw_root,
            metrics,
        )

        print(f"수집기간: {start_date.isoformat()} ~ {end_date.isoformat()}")
        print(f"대상기업: {len(companies)}개 / API 요청: {metrics.request_count}회")
        print(
            "결과: "
            f"발견 {counts['found']}건, 신규 {counts['new']}건, "
            f"변경 {counts['updated']}건, 제외·중복 {counts['skipped']}건"
        )
        if missing:
            print("고유번호 미확인 기업: " + ", ".join(missing))
        return 0
    except Exception as error:
        if engine is not None and (run_id is not None or source_run_id is not None):
            mark_failed(engine, run_id, source_run_id, metrics, error)
        print(f"수집 실패: {error}", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
