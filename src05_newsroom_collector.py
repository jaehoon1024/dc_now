#!/usr/bin/env python3
"""Collect minimum metadata from approved official newsroom list pages."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urljoin, unquote
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from src04_rss_collector import (
    CollectorError,
    USER_AGENT,
    canonicalize_url,
    load_env_file,
    resolve_database_url,
    store_items,
)


VERSION = "src05-1.1.0"
MAX_DOWNLOAD_BYTES = 2_000_000


class LguPressParser(HTMLParser):
    """Read cards from the official LG Uplus newsroom landing page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current: dict[str, str] | None = None
        self.capture: str | None = None
        self.items: list[dict[str, Any]] = []

    @staticmethod
    def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
        value = dict(attrs).get("class") or ""
        return set(value.split())

    def _finish_current(self) -> None:
        if self.current is None:
            return
        url = canonicalize_url(self.current.get("url", ""))
        title = " ".join(self.current.get("title", "").split())
        category = " ".join(self.current.get("category", "").split())
        published_at = None
        try:
            published_at = datetime.strptime(
                self.current.get("date", ""), "%Y.%m.%d"
            ).replace(tzinfo=ZoneInfo("Asia/Seoul"))
        except ValueError:
            pass
        if url and title and category == "보도자료":
            self.items.append(
                {
                    "title": title,
                    "canonical_url": url,
                    "published_at": published_at,
                    "published_raw": self.current.get("date", ""),
                    "guid": url,
                }
            )
        self.current = None
        self.capture = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        classes = self._classes(attrs)
        if tag == "div" and "latest-item" in classes:
            self._finish_current()
            self.current = {}
            return
        if self.current is None:
            return
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.current.setdefault("url", values["href"] or "")
        elif tag == "h3":
            self.capture = "title"
        elif tag == "span" and "category" in classes:
            self.capture = "category"
        elif tag == "span" and "date" in classes:
            self.capture = "date"

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h3", "span"}:
            self.capture = None

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.capture:
            self.current[self.capture] = self.current.get(self.capture, "") + data

    def close(self) -> None:
        super().close()
        self._finish_current()


def parse_lgu_press(payload: bytes) -> list[dict[str, Any]]:
    parser = LguPressParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    parser.close()
    unique: dict[str, dict[str, Any]] = {}
    for item in parser.items:
        unique[item["canonical_url"]] = item
    return list(unique.values())


class LguArchiveParser(HTMLParser):
    """Keep only title/date/URL from public press archive cards."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.current=None;self.capture=None;self.capture_tag=None;self.items=[]

    def finish(self):
        if self.current and self.current.get('title') and '보도자료' in self.current.get('category',''):
            title=' '.join(self.current['title'].split())
            url=canonicalize_url(self.current.get('url','').strip())
            if urlparse(url).hostname=='news.lguplus.com':
                raw=self.current.get('date','').strip()
                try: published=datetime.strptime(raw,'%Y.%m.%d').replace(tzinfo=ZoneInfo('Asia/Seoul'))
                except ValueError: published=None
                self.items.append(dict(title=title,canonical_url=url,published_at=published,published_raw=raw,guid=url))
        self.current=None;self.capture=None;self.capture_tag=None

    def handle_starttag(self,tag,attrs):
        values=dict(attrs);classes=set((values.get('class') or '').split())
        if tag=='li' and 'post-item-wrap' in classes:
            self.finish();self.current={};return
        if self.current is None:return
        if tag=='a' and 'post-title' in classes:
            self.current['url']=values.get('href','');self.capture='title';self.capture_tag='a'
        elif tag=='span' and 'post-date' in classes:self.capture='date';self.capture_tag='span'
        elif tag=='span' and 'post-category' in classes:self.capture='category';self.capture_tag='span'

    def handle_data(self,data):
        if self.current is not None and self.capture:self.current[self.capture]=self.current.get(self.capture,'')+data

    def handle_endtag(self,tag):
        if tag=='li' and self.current is not None:self.finish()
        elif tag==self.capture_tag:self.capture=None;self.capture_tag=None

    def close(self):
        super().close();self.finish()


def parse_lgu_archive(payload):
    parser=LguArchiveParser();parser.feed(payload.decode('utf-8',errors='replace'));parser.close()
    return list({x['canonical_url']:x for x in parser.items}.values())


def next_archive_url(payload,current_url):
    """Follow only the immediately next public archive page, never search/body URLs."""
    current=urlparse(current_url)
    if current.hostname!='news.lguplus.com':return None
    path=unquote(current.path).rstrip('/')
    match=re.search(r'/page/(\d+)$',path)
    base=path[:match.start()] if match else path
    if not base.startswith('/category/프레스센터/보도자료'):return None
    number=int(match.group(1)) if match else 1
    wanted=base+'/page/'+str(number+1)
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.links=[]
        def handle_starttag(self,tag,attrs):
            values=dict(attrs)
            if tag in {'a','link'} and values.get('href'):self.links.append(values['href'])
    parser=Links();parser.feed(payload.decode('utf-8',errors='replace'))
    for link in parser.links:
        full=urljoin(current_url,link.strip());candidate=urlparse(full)
        if candidate.scheme=='https' and candidate.hostname==current.hostname and not candidate.query and not candidate.fragment and unquote(candidate.path).rstrip('/')==wanted:return full
    return None


def article_batches(page,max_pages=3,since=None,fetch=None,sleep=None):
    fetch=fetch or fetch_page;sleep=sleep or time.sleep
    parser=PARSERS.get(str(page['parser_code']))
    if parser is None:raise CollectorError('지원하지 않는 뉴스룸 파서')
    current=page['page_url'];seen=set();page['pages_scanned']=0
    for _ in range(max_pages if page['parser_code']=='LGUPLUS_ARCHIVE_V1' else 1):
        if current in seen:raise CollectorError('뉴스룸 목록 페이지 순환')
        seen.add(current);payload=fetch({**page,'page_url':current});items=parser(payload)
        if not items:raise CollectorError('보도자료 목록 항목을 찾지 못했습니다.')
        page['pages_scanned']+=1
        dates=[x['published_at'].date() for x in items if x.get('published_at')]
        if dates:page['oldest_listed_date']=min(dates).isoformat()
        yield [x for x in items if not since or not x.get('published_at') or x['published_at'].date()>=since]
        if since and len(dates)==len(items) and min(dates)<since:
            page['scan_end']='date_limit';return
        if page['parser_code']!='LGUPLUS_ARCHIVE_V1':return
        current=next_archive_url(payload,current)
        if not current:page['scan_end']='archive_end';return
        if page['pages_scanned']<max_pages:sleep(max(30,int(page['request_interval_seconds'])))
    page['scan_end']='page_limit'


class SkbPressParser(HTMLParser):
    """Read press-release cards without opening article bodies."""

    DETAIL_PATTERN = re.compile(r"fn_read_view\(['\"]([0-9]+)['\"]\)")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current: dict[str, str] | None = None
        self.capture: str | None = None
        self.items: list[dict[str, Any]] = []

    @staticmethod
    def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
        return set((dict(attrs).get("class") or "").split())

    def _finish_current(self) -> None:
        if self.current is None:
            return
        key = self.current.get("key", "")
        title = " ".join(self.current.get("title", "").split())
        published_at = None
        try:
            published_at = datetime.strptime(
                self.current.get("date", ""), "%Y.%m.%d"
            ).replace(tzinfo=ZoneInfo("Asia/Seoul"))
        except ValueError:
            pass
        if key and title:
            url = (
                "https://www.skbroadband.com/kor/pr/press_detail.do?"
                f"keynum={key}&menu_id=K05010000"
            )
            self.items.append(
                {
                    "title": title,
                    "canonical_url": canonicalize_url(url),
                    "published_at": published_at,
                    "published_raw": self.current.get("date", ""),
                    "guid": key,
                }
            )
        self.current = None
        self.capture = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attrs)
        if tag == "a":
            match = self.DETAIL_PATTERN.search(values.get("href") or "")
            if match:
                self._finish_current()
                self.current = {"key": match.group(1)}
                return
        if self.current is None:
            return
        classes = self._classes(attrs)
        if tag == "p" and classes.intersection(
            {"news_graybox-tit", "download_name"}
        ):
            self.capture = "title"
        elif tag in {"p", "span"} and classes.intersection(
            {"news_graybox-date", "download_date"}
        ):
            self.capture = "date"

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "span"}:
            self.capture = None

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.capture:
            self.current[self.capture] = self.current.get(self.capture, "") + data

    def close(self) -> None:
        super().close()
        self._finish_current()


def parse_skb_press(payload: bytes) -> list[dict[str, Any]]:
    parser = SkbPressParser()
    parser.feed(payload.decode("utf-8", errors="replace"))
    parser.close()
    unique: dict[str, dict[str, Any]] = {}
    for item in parser.items:
        unique[item["canonical_url"]] = item
    return list(unique.values())


PARSERS = {
    "LGUPLUS_PRESS_V1": parse_lgu_press,
    "LGUPLUS_ARCHIVE_V1": parse_lgu_archive,
    "SKB_PRESS_V1": parse_skb_press,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="승인된 기업 뉴스룸에서 최소 메타데이터 수집"
    )
    parser.add_argument("--source-code")
    parser.add_argument("--max-pages",type=int,default=3,choices=range(1,201),metavar="1..200")
    parser.add_argument("--since",type=date.fromisoformat,help="과거 목록 반입 시작일 YYYY-MM-DD")
    parser.add_argument(
        "--trigger",
        choices=("MANUAL", "SCHEDULED", "RETRY", "BACKFILL"),
        default="MANUAL",
    )
    return parser.parse_args()


def load_pages(engine: Any, source_code: str | None) -> list[dict[str, Any]]:
    condition = " AND sr.source_code = :source_code" if source_code else ""
    parameters = {"source_code": source_code} if source_code else {}
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT sp.page_id, sp.source_id, sp.page_code AS feed_code,
                       sp.page_name AS feed_name, sp.page_url, sp.parser_code,
                       sp.filter_keywords, sp.request_interval_seconds,
                       sr.source_code, sr.source_name, sr.default_source_grade
                FROM source_page sp
                JOIN source_registry sr ON sr.source_id = sp.source_id
                WHERE sp.active = true
                  AND sr.active = true
                  AND sr.terms_review_status IN ('ALLOWED', 'LIMITED')
                  AND sr.collection_policy = 'METADATA_ONLY'
                  AND sr.content_storage_policy = 'METADATA_ONLY'
                """
                + condition
                + " ORDER BY sr.source_code, sp.page_code"
            ),
            parameters,
        ).mappings().all()
    return [dict(row) for row in rows]


def fetch_page(page: dict[str, Any]) -> bytes:
    request = Request(
        str(page["page_url"]),
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read(MAX_DOWNLOAD_BYTES + 1)
            if len(payload) > MAX_DOWNLOAD_BYTES:
                raise CollectorError("뉴스룸 응답이 다운로드 제한을 초과했습니다.")
            return payload
    except HTTPError as error:
        raise CollectorError(
            f"{page['feed_code']} HTTP 오류: {error.code} {error.reason}"
        ) from error


def create_run(engine: Any, trigger: str, total: int) -> Any:
    with engine.begin() as connection:
        return connection.execute(
            text(
                """
                INSERT INTO collection_run (
                    job_name, trigger_type, requested_by, started_at,
                    run_status, total_source_count, host_name,
                    application_version
                ) VALUES (
                    :job, :trigger, :requested_by,
                    CURRENT_TIMESTAMP, 'RUNNING', :total, :host, :version
                ) RETURNING collection_run_id
                """
            ),
            {
                "job": "NEWSROOM_HISTORY_BACKFILL" if trigger=="BACKFILL" else "NEWSROOM_DAILY",
                "trigger": trigger,
                "requested_by": os.getenv("USER", "dc-platform"),
                "total": total,
                "host": socket.gethostname(),
                "version": VERSION,
            },
        ).scalar_one()


def finish_run(engine: Any, run_id: Any, success: int, failed: int,
               new: int, updated: int, errors: list[str]) -> None:
    status = "SUCCESS" if failed == 0 else "FAILED" if success == 0 else "PARTIAL"
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE collection_run
                SET finished_at = CURRENT_TIMESTAMP, run_status = :status,
                    success_source_count = :success,
                    failed_source_count = :failed,
                    new_document_count = :new,
                    updated_document_count = :updated,
                    error_summary = :errors
                WHERE collection_run_id = :run_id
                """
            ),
            {
                "run_id": run_id, "status": status, "success": success,
                "failed": failed, "new": new, "updated": updated,
                "errors": " | ".join(errors)[:4000] if errors else None,
            },
        )


def mark_page(engine: Any, page_id: Any, error: Exception | None) -> None:
    with engine.begin() as connection:
        if error is None:
            connection.execute(
                text(
                    """
                    UPDATE source_page
                    SET last_polled_at = CURRENT_TIMESTAMP,
                        last_success_at = CURRENT_TIMESTAMP,
                        consecutive_failure_count = 0, last_error = NULL
                    WHERE page_id = :page_id
                    """
                ),
                {"page_id": page_id},
            )
        else:
            connection.execute(
                text(
                    """
                    UPDATE source_page
                    SET last_polled_at = CURRENT_TIMESTAMP,
                        consecutive_failure_count = consecutive_failure_count + 1,
                        last_error = :error
                    WHERE page_id = :page_id
                    """
                ),
                {"page_id": page_id, "error": str(error)[:2000]},
            )


def main() -> int:
    load_env_file()
    args = parse_args()
    engine = create_engine(resolve_database_url(), pool_pre_ping=True)
    run_id = None
    successes = failures = new = updated = 0
    errors: list[str] = []
    try:
        pages = load_pages(engine, args.source_code)
        if not pages:
            raise CollectorError("실행 가능한 뉴스룸 페이지가 없습니다.")
        run_id = create_run(engine, args.trigger, len(pages))
        raw_root = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
        for page in pages:
            try:
                page["filter_mode"] = "KEYWORD_REQUIRED"
                from src04_rss_collector import Counts
                counts=Counts()
                for items in article_batches(page,args.max_pages,args.since):
                    if not items:continue
                    batch=store_items(engine,page,items,raw_root,collection_kind="newsroom",collector_version=VERSION,parser_name="newsroom-metadata",external_id_prefix="newsroom")
                    counts.add(batch)
                successes += 1
                new += counts.new
                updated += counts.updated
                mark_page(engine, page["page_id"], None)
                print(f"목록 범위 {page['source_code']}: {page.get('pages_scanned',1)}페이지 / 최저 게시일 {page.get('oldest_listed_date','미확인')} / 종료 {page.get('scan_end','single_page')}",flush=True)
                print(
                    f"- {page['source_code']}: 발견 {counts.found}, "
                    f"신규 {counts.new}, 변경 {counts.updated}, "
                    f"제외·중복 {counts.skipped}"
                )
            except Exception as error:
                failures += 1
                message = f"{page['feed_code']}: {error}"
                errors.append(message)
                mark_page(engine, page["page_id"], error)
                print(f"뉴스룸 실패 - {message}", file=sys.stderr)
        finish_run(engine, run_id, successes, failures, new, updated, errors)
        return 1 if failures else 0
    except Exception as error:
        if run_id is not None:
            finish_run(engine, run_id, successes, max(failures, 1), new, updated,
                       errors or [str(error)])
        print(f"뉴스룸 수집 실패: {error}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
