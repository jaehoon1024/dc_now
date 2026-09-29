#!/usr/bin/env python3
"""Check daily collectors and optionally send a minimal webhook alert."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.request import Request, urlopen

from sqlalchemy import create_engine, text

from src04_rss_collector import load_env_file, resolve_database_url


VERSION = "src09-1.0.0"
EXPECTED_JOBS = ("OPENDART_DAILY", "RSS_DAILY", "NEWSROOM_DAILY")
HEALTHY_STATUSES = {"SUCCESS"}


@dataclass(frozen=True)
class Alert:
    job_name: str
    reason: str
    run_status: str | None = None
    finished_at: datetime | None = None
    failed_source_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_name": self.job_name,
            "reason": self.reason,
            "run_status": self.run_status,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "failed_source_count": self.failed_source_count,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="일일 수집 작업 실패·지연 점검")
    parser.add_argument("--max-age-hours", type=float, default=36.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--no-webhook", action="store_true")
    return parser.parse_args()


def load_latest_runs(engine: Any) -> dict[str, dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT DISTINCT ON (job_name)
                       job_name, run_status, started_at, finished_at,
                       failed_source_count
                FROM collection_run
                WHERE job_name = ANY(:job_names)
                ORDER BY job_name, started_at DESC NULLS LAST, created_at DESC
                """
            ),
            {"job_names": list(EXPECTED_JOBS)},
        ).mappings().all()
    return {str(row["job_name"]): dict(row) for row in rows}


def evaluate_runs(
    latest: dict[str, dict[str, Any]],
    now: datetime,
    max_age: timedelta,
) -> list[Alert]:
    alerts: list[Alert] = []
    for job_name in EXPECTED_JOBS:
        run = latest.get(job_name)
        if run is None:
            alerts.append(Alert(job_name, "NO_RUN"))
            continue

        status = str(run.get("run_status") or "UNKNOWN")
        finished_at = run.get("finished_at")
        failed_count = int(run.get("failed_source_count") or 0)
        if status not in HEALTHY_STATUSES:
            alerts.append(
                Alert(job_name, "UNHEALTHY_STATUS", status, finished_at, failed_count)
            )
            continue

        reference_time = finished_at or run.get("started_at")
        if reference_time is None or now - reference_time > max_age:
            alerts.append(Alert(job_name, "STALE", status, finished_at, failed_count))
    return alerts


def build_payload(alerts: list[Alert], checked_at: datetime) -> dict[str, Any]:
    return {
        "service": "dc-platform",
        "event": "collection_health_alert",
        "checked_at": checked_at.isoformat(),
        "alert_count": len(alerts),
        "alerts": [alert.as_dict() for alert in alerts],
    }


def send_webhook(url: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": VERSION},
        method="POST",
    )
    timeout = float(os.getenv("COLLECTION_ALERT_TIMEOUT_SECONDS", "10"))
    with urlopen(request, timeout=timeout) as response:
        if not 200 <= int(response.status) < 300:
            raise RuntimeError(f"webhook HTTP 상태 {response.status}")


def main() -> int:
    load_env_file()
    args = parse_args()
    if args.max_age_hours <= 0:
        raise SystemExit("--max-age-hours는 0보다 커야 합니다.")

    engine = create_engine(resolve_database_url(), pool_pre_ping=True)
    now = datetime.now(timezone.utc)
    try:
        alerts = evaluate_runs(
            load_latest_runs(engine), now, timedelta(hours=args.max_age_hours)
        )
    finally:
        engine.dispose()

    payload = build_payload(alerts, now)
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False))
    elif alerts:
        for alert in alerts:
            print(
                f"ALERT {alert.job_name} {alert.reason} "
                f"status={alert.run_status or '-'} failed={alert.failed_source_count}"
            )
    else:
        print("OK 모든 일일 수집 작업이 정상 범위입니다.")

    webhook_url = os.getenv("COLLECTION_ALERT_WEBHOOK_URL", "").strip()
    if alerts and webhook_url and not args.no_webhook:
        try:
            send_webhook(webhook_url, payload)
        except Exception as error:
            print(f"알림 전송 실패: {type(error).__name__}", file=sys.stderr)
            return 3
    return 2 if alerts else 0


if __name__ == "__main__":
    raise SystemExit(main())
