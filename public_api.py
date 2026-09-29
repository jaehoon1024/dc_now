#!/usr/bin/env python3
"""Read-only HTTP API for reviewed public data-center records."""

from __future__ import annotations

import argparse
import html
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs
from wsgiref.simple_server import WSGIRequestHandler, make_server

from sqlalchemy import create_engine, text

from src04_rss_collector import load_env_file, resolve_database_url


VERSION = "public-api-1.0.0"
SITE_COLUMNS = (
    "site_code", "site_name", "address_standard", "sido", "sigungu",
    "latitude", "longitude", "lifecycle_group", "owner_names",
    "operator_names", "operating_grid_intake_mw", "operating_it_load_mw",
    "development_grid_intake_mw", "development_it_load_mw",
    "earliest_rfs_date", "latest_data_update",
)
STATUSES = {"OPERATING", "DEVELOPMENT", "MIXED", "ON_HOLD", "UNKNOWN"}
DASHBOARD_PATH = __import__("pathlib").Path(__file__).resolve().parent / "dashboard" / "public.html"


def json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def parse_positive_int(value: str | None, default: int, maximum: int) -> int:
    if value is None or value == "":
        return default
    parsed = int(value)
    if parsed < 1:
        raise ValueError("positive integer required")
    return min(parsed, maximum)


def site_query(
    sido: str | None, status: str | None, limit: int, offset: int
) -> tuple[str, dict[str, Any]]:
    if status and status not in STATUSES:
        raise ValueError("invalid status")
    conditions = ["public_visible = true", "review_status = 'CONFIRMED'"]
    parameters: dict[str, Any] = {"limit": limit, "offset": offset}
    if sido:
        conditions.append("sido = :sido")
        parameters["sido"] = sido
    if status:
        conditions.append("lifecycle_group = :status")
        parameters["status"] = status
    return (
        "SELECT " + ", ".join(SITE_COLUMNS)
        + ", count(*) OVER() AS total_count FROM v_site_map WHERE "
        + " AND ".join(conditions)
        + " ORDER BY sido NULLS LAST, sigungu NULLS LAST, site_name "
        + "LIMIT :limit OFFSET :offset",
        parameters,
    )


class PublicRepository:
    def __init__(self, engine: Any):
        self.engine = engine

    def sites(self, sido: str | None, status: str | None, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        query, parameters = site_query(sido, status, limit, offset)
        with self.engine.connect() as connection:
            rows = [dict(row) for row in connection.execute(text(query), parameters).mappings()]
        total = int(rows[0].pop("total_count")) if rows else 0
        return rows, total

    def target_summary(self) -> dict[str, int]:
        with self.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT count(*) AS target_total,
                       count(*) FILTER (
                           WHERE public_visible = true AND review_status = 'CONFIRMED'
                       ) AS public_total,
                       count(*) FILTER (
                           WHERE review_status = 'NEEDS_EVIDENCE'
                       ) AS needs_evidence_total
                FROM dc_site WHERE record_status = 'ACTIVE'
            """)).mappings().one()
        return {key: int(value or 0) for key, value in row.items()}

    def regions(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT COALESCE(sido, '미확인') AS sido, lifecycle_group,
                           count(*) AS site_count,
                           sum(operating_project_count) AS operating_project_count,
                           sum(development_project_count) AS development_project_count,
                           sum(operating_it_load_mw) AS operating_it_load_mw,
                           sum(development_it_load_mw) AS development_it_load_mw,
                           max(latest_data_update) AS latest_data_update
                    FROM v_site_map
                    WHERE public_visible = true AND review_status = 'CONFIRMED'
                    GROUP BY COALESCE(sido, '미확인'), lifecycle_group
                    ORDER BY sido, lifecycle_group
                    """
                )
            ).mappings().all()
        return [dict(row) for row in rows]

    def site_detail(self, site_code: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            site = connection.execute(
                text(
                    """
                    SELECT site_code, site_name, address_standard, sido, sigungu,
                           latitude, longitude, lifecycle_group, owner_names,
                           operator_names, developer_names, dbo_provider_names,
                           (SELECT string_agg(DISTINCT c.standard_name, ', ')
                            FROM company_participation cp JOIN company c ON c.company_id=cp.company_id
                            WHERE cp.scope_type='SITE' AND cp.scope_id=v_site_map.site_id
                              AND cp.role_code='ASSET_MANAGER' AND cp.review_status='CONFIRMED') AS asset_manager_names,
                           (SELECT string_agg(DISTINCT c.standard_name, ', ')
                            FROM company_participation cp JOIN company c ON c.company_id=cp.company_id
                            WHERE cp.scope_type='SITE' AND cp.scope_id=v_site_map.site_id
                              AND cp.role_code='BUILDER' AND cp.review_status='CONFIRMED') AS builder_names,
                           operating_grid_intake_mw, operating_it_load_mw,
                           development_grid_intake_mw, development_it_load_mw,
                           earliest_rfs_date, latest_data_update
                    FROM v_site_map
                    WHERE site_code = :site_code AND public_visible = true
                      AND review_status = 'CONFIRMED'
                    """
                ), {"site_code": site_code},
            ).mappings().first()
            if site is None:
                return None
            projects = connection.execute(
                text(
                    """
                    SELECT p.project_code, p.project_name, p.status_code,
                           p.planned_rfs_date, p.rfs_date
                    FROM dc_project p JOIN dc_site s ON s.site_id = p.site_id
                    WHERE s.site_code = :site_code AND s.public_visible = true
                      AND s.review_status = 'CONFIRMED' AND p.public_visible = true
                      AND p.review_status = 'CONFIRMED' AND p.record_status = 'ACTIVE'
                    ORDER BY COALESCE(p.rfs_date, p.planned_rfs_date), p.project_name
                    """
                ), {"site_code": site_code},
            ).mappings().all()
        result = dict(site)
        result["projects"] = [dict(row) for row in projects]
        return result

    def companies(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                WITH names AS (
                    SELECT trim(name) AS company_name, lifecycle_group,
                           operating_it_load_mw, development_it_load_mw, site_code
                    FROM v_site_map,
                    LATERAL regexp_split_to_table(
                        concat_ws(',', owner_names, operator_names, developer_names), ','
                    ) AS name
                    WHERE public_visible = true AND review_status = 'CONFIRMED'
                )
                SELECT company_name, count(DISTINCT site_code) AS site_count,
                       count(DISTINCT site_code) FILTER (WHERE lifecycle_group IN ('OPERATING','MIXED')) AS operating_site_count,
                       count(DISTINCT site_code) FILTER (WHERE lifecycle_group IN ('DEVELOPMENT','MIXED')) AS development_site_count,
                       sum(operating_it_load_mw) AS operating_it_load_mw,
                       sum(development_it_load_mw) AS development_it_load_mw
                FROM names WHERE company_name <> '' GROUP BY company_name
                ORDER BY site_count DESC, company_name
            """)).mappings().all()
        return [dict(row) for row in rows]

    def yearly(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT extract(year FROM COALESCE(p.rfs_date, p.planned_rfs_date))::integer AS supply_year,
                       CASE WHEN p.rfs_date IS NULL THEN 'PLANNED' ELSE 'ACTUAL' END AS date_basis,
                       count(DISTINCT p.project_id) AS project_count
                FROM dc_project p JOIN dc_site s ON s.site_id = p.site_id
                WHERE s.public_visible = true AND s.review_status = 'CONFIRMED'
                  AND p.public_visible = true AND p.review_status = 'CONFIRMED'
                  AND p.record_status = 'ACTIVE'
                  AND COALESCE(p.rfs_date, p.planned_rfs_date) IS NOT NULL
                GROUP BY supply_year, date_basis ORDER BY supply_year, date_basis
            """)).mappings().all()
        return [dict(row) for row in rows]

    def collection_status(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT DISTINCT ON (job_name) job_name, run_status, started_at,
                       finished_at, total_source_count, success_source_count,
                       failed_source_count, new_document_count
                FROM collection_run ORDER BY job_name, started_at DESC NULLS LAST
            """)).mappings().all()
        return [dict(row) for row in rows]

    def health(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))


def json_response(start_response: Any, status: str, payload: Any) -> list[bytes]:
    body = json.dumps(payload, ensure_ascii=False, default=json_value).encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "public, max-age=60" if status.startswith("200") else "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ],
    )
    return [body]


def html_response(start_response: Any, body: str) -> list[bytes]:
    encoded = body.encode("utf-8")
    start_response("200 OK", [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(encoded))),
        ("Cache-Control", "no-cache"),
        ("X-Content-Type-Options", "nosniff"),
        ("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'"),
    ])
    return [encoded]


def make_application(repository: Any):
    def application(environ: dict[str, Any], start_response: Any) -> list[bytes]:
        if environ.get("REQUEST_METHOD") != "GET":
            return json_response(start_response, "405 Method Not Allowed", {"error": "method_not_allowed"})
        path = environ.get("PATH_INFO", "")
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=False)
        try:
            if path == "/api/v1/healthz":
                repository.health()
                return json_response(start_response, "200 OK", {"status": "ok", "version": VERSION})
            if path == "/api/v1/regions":
                return json_response(start_response, "200 OK", {"items": repository.regions()})
            if path == "/api/v1/companies":
                return json_response(start_response, "200 OK", {"items": repository.companies()})
            if path == "/api/v1/yearly":
                return json_response(start_response, "200 OK", {"items": repository.yearly()})
            if path == "/api/v1/collection-status":
                return json_response(start_response, "200 OK", {"items": repository.collection_status()})
            if path.startswith("/api/v1/sites/"):
                site_code = path.removeprefix("/api/v1/sites/")
                if not site_code or len(site_code) > 30:
                    raise ValueError("invalid site code")
                item = repository.site_detail(site_code)
                if item is None:
                    return json_response(start_response, "404 Not Found", {"error": "not_found"})
                return json_response(start_response, "200 OK", item)
            if path == "/api/v1/sites":
                limit = parse_positive_int(query.get("limit", [None])[0], 100, 500)
                page = parse_positive_int(query.get("page", [None])[0], 1, 100000)
                sido = query.get("sido", [None])[0]
                status = query.get("status", [None])[0]
                rows, total = repository.sites(sido, status, limit, (page - 1) * limit)
                return json_response(
                    start_response, "200 OK",
                    {"items": rows, "page": page, "limit": limit, "total": total},
                )
            if path == "/":
                return html_response(start_response, DASHBOARD_PATH.read_text(encoding="utf-8"))
            return json_response(start_response, "404 Not Found", {"error": "not_found"})
        except (ValueError, TypeError):
            return json_response(start_response, "400 Bad Request", {"error": "invalid_parameter"})
        except Exception:
            return json_response(start_response, "503 Service Unavailable", {"error": "service_unavailable"})

    return application


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.client_address[0]} {args[0]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="공개 데이터센터 조회 API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    load_env_file()
    engine = create_engine(
        resolve_database_url(), pool_pre_ping=True,
        connect_args={"options": "-c default_transaction_read_only=on -c statement_timeout=10000"},
    )
    try:
        with make_server(args.host, args.port, make_application(PublicRepository(engine)), handler_class=QuietHandler) as server:
            print(f"공개 API 시작: http://{args.host}:{args.port}")
            server.serve_forever()
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
