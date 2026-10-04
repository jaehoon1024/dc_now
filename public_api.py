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
    conditions = [
        "public_visible = true", "review_status = 'CONFIRMED'",
        "EXISTS (SELECT 1 FROM dc_site scope_site "
        "WHERE scope_site.site_code=v_site_map.site_code "
        "AND scope_site.commercial_scope_status='IN_SCOPE' "
        "AND scope_site.commercial_review_status='CONFIRMED')",
    ]
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

    def tracking_sites(self) -> list[dict[str, Any]]:
        """Return minimal public tracking fields for every active target.

        Candidate rows remain explicitly labelled and are excluded from the
        confirmed market aggregates exposed by the other repository methods.
        """
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT v.site_code, v.site_name, v.address_standard,
                       v.sido, v.sigungu, v.latitude, v.longitude,
                       v.lifecycle_group, v.owner_names, v.operator_names,
                       v.operating_grid_intake_mw, v.operating_it_load_mw,
                       v.development_grid_intake_mw, v.development_it_load_mw,
                       v.earliest_rfs_date, v.latest_data_update,
                       (SELECT p.planned_rfs_period
                        FROM dc_project p
                        WHERE p.site_id=v.site_id AND p.record_status='ACTIVE'
                          AND p.review_status='CONFIRMED'
                          AND p.planned_rfs_period IS NOT NULL
                        ORDER BY p.planned_rfs_date NULLS LAST, p.created_at
                        LIMIT 1) AS earliest_rfs_period,
                       (SELECT sum(cs.normalized_value_mw)
                        FROM capacity_snapshot cs
                        JOIN dc_project p ON p.project_id=cs.scope_id
                        WHERE cs.scope_type='PROJECT' AND p.site_id=v.site_id
                          AND p.record_status='ACTIVE'
                          AND cs.capacity_type_code='ANNOUNCED_UNCLASSIFIED_MW'
                          AND cs.capacity_stage IN ('ANNOUNCED','SECURED','DESIGNED','UNDER_CONSTRUCTION')
                          AND cs.review_status='CONFIRMED') AS development_announced_capacity_mw,
                       v.review_status, v.public_visible,
                       v.location_precision, v.coordinate_quality,
                       s.commercial_scope_status, s.commercial_model,
                       s.commercial_review_status, s.commercial_scope_note,
                       s.commercial_source_url,
                       s.facility_scope, s.facility_review_status,
                       s.facility_scope_note, s.facility_source_url,
                       (SELECT string_agg(DISTINCT c.standard_name, ', ' ORDER BY c.standard_name)
                        FROM company_participation cp
                        JOIN company c ON c.company_id=cp.company_id
                        WHERE cp.scope_type='SITE' AND cp.scope_id=v.site_id
                          AND cp.review_status IN ('CONFIRMED','CANDIDATE')) AS tracked_company_names,
                       (v.site_name LIKE '%%수집 검증 대상%%') AS discovery_target,
                       CASE
                           WHEN v.public_visible=true AND v.review_status='CONFIRMED'
                               THEN 'PUBLIC_CONFIRMED'
                           WHEN v.site_name LIKE '%%수집 검증 대상%%'
                               THEN 'DISCOVERY_TARGET'
                           ELSE 'REVIEW_REQUIRED'
                       END AS tracking_status
                FROM v_site_map v
                JOIN dc_site s ON s.site_id=v.site_id
                WHERE s.record_status='ACTIVE'
                  AND (s.commercial_scope_status <> 'OUT_OF_SCOPE'
                       OR s.facility_scope IN ('ENTERPRISE','CLOUD_SELF_USE'))
                ORDER BY v.public_visible DESC, v.sido NULLS LAST,
                         v.sigungu NULLS LAST, v.site_name
            """)).mappings().all()
        return [dict(row) for row in rows]

    def target_summary(self) -> dict[str, int]:
        with self.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT count(*) FILTER (
                           WHERE commercial_scope_status <> 'OUT_OF_SCOPE'
                       ) AS target_total,
                       count(*) FILTER (
                           WHERE public_visible = true AND review_status = 'CONFIRMED'
                             AND commercial_scope_status = 'IN_SCOPE'
                             AND commercial_review_status = 'CONFIRMED'
                       ) AS public_total,
                       count(*) FILTER (
                           WHERE commercial_scope_status = 'REVIEW_REQUIRED'
                              OR commercial_review_status = 'NEEDS_EVIDENCE'
                       ) AS needs_evidence_total,
                       count(*) FILTER (
                           WHERE commercial_scope_status = 'IN_SCOPE'
                             AND commercial_review_status = 'CONFIRMED'
                       ) AS commercial_confirmed_total,
                       count(*) FILTER (
                           WHERE commercial_scope_status = 'OUT_OF_SCOPE'
                       ) AS out_of_scope_total,
                       count(*) FILTER (
                           WHERE facility_scope = 'ENTERPRISE'
                       ) AS enterprise_total,
                       count(*) FILTER (
                           WHERE facility_scope = 'CLOUD_SELF_USE'
                       ) AS cloud_self_use_total,
                       count(*) FILTER (
                           WHERE facility_scope IN ('ENTERPRISE','CLOUD_SELF_USE')
                             AND facility_review_status = 'CONFIRMED'
                       ) AS noncommercial_confirmed_total
                FROM dc_site WHERE record_status = 'ACTIVE'
            """)).mappings().one()
        return {key: int(value or 0) for key, value in row.items()}

    def regions(self) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT COALESCE(v.sido, '미확인') AS sido, v.lifecycle_group,
                           count(*) AS site_count,
                           sum(operating_project_count) AS operating_project_count,
                           sum(development_project_count) AS development_project_count,
                           sum(operating_it_load_mw) AS operating_it_load_mw,
                           sum(development_it_load_mw) AS development_it_load_mw,
                           max(latest_data_update) AS latest_data_update
                    FROM v_site_map v
                    JOIN dc_site s ON s.site_id=v.site_id
                    WHERE v.public_visible = true AND v.review_status = 'CONFIRMED'
                      AND s.commercial_scope_status='IN_SCOPE'
                      AND s.commercial_review_status='CONFIRMED'
                    GROUP BY COALESCE(v.sido, '미확인'), v.lifecycle_group
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
                    SELECT v.site_code, v.site_name, v.address_standard, v.sido, v.sigungu,
                           v.latitude, v.longitude, v.lifecycle_group, v.owner_names,
                           v.operator_names, v.developer_names, v.dbo_provider_names,
                           (SELECT string_agg(DISTINCT c.standard_name, ', ')
                            FROM company_participation cp JOIN company c ON c.company_id=cp.company_id
                            WHERE cp.scope_type='SITE' AND cp.scope_id=v.site_id
                              AND cp.role_code='ASSET_MANAGER' AND cp.review_status='CONFIRMED') AS asset_manager_names,
                           (SELECT string_agg(DISTINCT c.standard_name, ', ')
                            FROM company_participation cp JOIN company c ON c.company_id=cp.company_id
                            WHERE cp.scope_type='SITE' AND cp.scope_id=v.site_id
                              AND cp.role_code='BUILDER' AND cp.review_status='CONFIRMED') AS builder_names,
                           v.operating_grid_intake_mw, v.operating_it_load_mw,
                           v.development_grid_intake_mw, v.development_it_load_mw,
                           v.earliest_rfs_date, v.latest_data_update,
                           (SELECT p.planned_rfs_period
                            FROM dc_project p
                            WHERE p.site_id=v.site_id AND p.record_status='ACTIVE'
                              AND p.review_status='CONFIRMED'
                              AND p.planned_rfs_period IS NOT NULL
                            ORDER BY p.planned_rfs_date NULLS LAST, p.created_at
                            LIMIT 1) AS earliest_rfs_period,
                           (SELECT sum(cs.normalized_value_mw)
                            FROM capacity_snapshot cs
                            JOIN dc_project p ON p.project_id=cs.scope_id
                            WHERE cs.scope_type='PROJECT' AND p.site_id=v.site_id
                              AND p.record_status='ACTIVE'
                              AND cs.capacity_type_code='ANNOUNCED_UNCLASSIFIED_MW'
                              AND cs.capacity_stage IN ('ANNOUNCED','SECURED','DESIGNED','UNDER_CONSTRUCTION')
                              AND cs.review_status='CONFIRMED') AS development_announced_capacity_mw,
                           s.commercial_scope_status, s.commercial_model,
                           s.commercial_review_status, s.commercial_scope_note,
                           s.commercial_source_url, s.facility_scope,
                           s.facility_review_status, s.facility_scope_note,
                           s.facility_source_url
                    FROM v_site_map v JOIN dc_site s ON s.site_id=v.site_id
                    WHERE v.site_code = :site_code AND v.public_visible = true
                      AND v.review_status = 'CONFIRMED'
                      AND ((s.commercial_scope_status='IN_SCOPE'
                            AND s.commercial_review_status='CONFIRMED')
                           OR s.facility_scope IN ('ENTERPRISE','CLOUD_SELF_USE'))
                    """
                ), {"site_code": site_code},
            ).mappings().first()
            if site is None:
                return None
            projects = connection.execute(
                text(
                    """
                    SELECT p.project_code, p.project_name, p.status_code,
                           p.planned_rfs_date, p.planned_rfs_precision,
                           p.planned_rfs_period, p.rfs_date
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
                WITH relations AS (
                    SELECT DISTINCT cp.company_id, s.site_id
                    FROM company_participation cp
                    JOIN dc_site s ON cp.scope_type='SITE' AND cp.scope_id=s.site_id
                    WHERE cp.review_status='CONFIRMED'
                ), portfolio AS (
                    SELECT r.company_id, v.site_code, v.lifecycle_group,
                           v.operating_it_load_mw, v.development_it_load_mw
                    FROM relations r JOIN v_site_map v ON v.site_id=r.site_id
                    JOIN dc_site s ON s.site_id=r.site_id
                    WHERE v.public_visible=true AND v.review_status='CONFIRMED'
                      AND s.commercial_scope_status='IN_SCOPE'
                      AND s.commercial_review_status='CONFIRMED'
                ), facility_portfolio AS (
                    SELECT cp.company_id,
                           count(DISTINCT s.site_code) FILTER (
                               WHERE s.facility_scope='ENTERPRISE'
                           ) AS enterprise_site_count,
                           count(DISTINCT s.site_code) FILTER (
                               WHERE s.facility_scope='CLOUD_SELF_USE'
                           ) AS cloud_self_use_site_count,
                           count(DISTINCT s.site_code) FILTER (
                               WHERE s.facility_review_status='NEEDS_EVIDENCE'
                           ) AS facility_review_site_count
                    FROM company_participation cp
                    JOIN dc_site s ON cp.scope_type='SITE' AND cp.scope_id=s.site_id
                    WHERE cp.review_status IN ('CONFIRMED','CANDIDATE')
                      AND s.facility_scope IN ('ENTERPRISE','CLOUD_SELF_USE')
                    GROUP BY cp.company_id
                )
                SELECT c.standard_name AS company_name,
                       count(DISTINCT p.site_code) AS site_count,
                       count(DISTINCT site_code) FILTER (WHERE lifecycle_group = 'OPERATING') AS operating_site_count,
                       count(DISTINCT site_code) FILTER (WHERE lifecycle_group = 'DEVELOPMENT') AS development_site_count,
                       count(DISTINCT site_code) FILTER (WHERE lifecycle_group = 'MIXED') AS mixed_site_count,
                       sum(operating_it_load_mw) AS operating_it_load_mw,
                       sum(development_it_load_mw) AS development_it_load_mw,
                       COALESCE(max(f.enterprise_site_count),0) AS enterprise_site_count,
                       COALESCE(max(f.cloud_self_use_site_count),0) AS cloud_self_use_site_count,
                       COALESCE(max(f.facility_review_site_count),0) AS facility_review_site_count
                FROM company c LEFT JOIN portfolio p ON p.company_id=c.company_id
                LEFT JOIN facility_portfolio f ON f.company_id=c.company_id
                WHERE c.record_status='ACTIVE' AND c.review_status='CONFIRMED'
                GROUP BY c.company_id,c.standard_name
                ORDER BY count(DISTINCT p.site_code) DESC,c.standard_name
            """)).mappings().all()
        return [dict(row) for row in rows]

    def player_intelligence(self) -> list[dict[str, Any]]:
        """Summarize three-year evidence discovery for priority market players."""
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                WITH players(player_name, player_type, aliases) AS (VALUES
                    ('LG CNS','IT서비스·운영사',ARRAY['LG CNS','LG씨엔에스','엘지씨엔에스']),
                    ('현대자동차','기업 전용센터',ARRAY['현대자동차 데이터센터','현대차 데이터센터','현대자동차 IT센터']),
                    ('삼성전자','기업 전용센터',ARRAY['삼성전자 데이터센터','삼성전자 IT센터']),
                    ('SK하이닉스','기업 전용센터',ARRAY['SK하이닉스 데이터센터','SK하이닉스 IT센터']),
                    ('삼성SDS','IT서비스·운영사',ARRAY['삼성SDS','삼성 SDS','Samsung SDS']),
                    ('kt cloud','통신·운영사',ARRAY['kt cloud','KT클라우드','케이티클라우드']),
                    ('SK브로드밴드','통신·운영사',ARRAY['SK브로드밴드','SK broadband']),
                    ('LG유플러스','통신·운영사',ARRAY['LG유플러스','LG U+','LG Uplus']),
                    ('롯데이노베이트','IT서비스·운영사',ARRAY['롯데이노베이트','롯데정보통신']),
                    ('네이버클라우드','클라우드·운영사',ARRAY['네이버클라우드','NAVER Cloud']),
                    ('NHN클라우드','클라우드·운영사',ARRAY['NHN클라우드','NHN Cloud']),
                    ('KINX','코로케이션 운영사',ARRAY['KINX','케이아이엔엑스']),
                    ('카카오','클라우드·운영사',ARRAY['카카오 데이터센터','카카오 DC']),
                    ('코람코자산운용','자산운용사',ARRAY['코람코자산운용','코람코자산신탁','코람코']),
                    ('이지스자산운용','자산운용사',ARRAY['이지스자산운용','IGIS']),
                    ('마스턴투자운용','자산운용사',ARRAY['마스턴투자운용','마스턴']),
                    ('ESR켄달스퀘어','자산운용사',ARRAY['ESR켄달스퀘어','ESR KendallSquare','ESR Kendall Square']),
                    ('ESR Group','개발·투자사',ARRAY['ESR Group','ESR그룹']),
                    ('Wide Creek Asset Management','자산운용사',ARRAY['Wide Creek','와이드크릭']),
                    ('이도','개발·운영사',ARRAY['이도 데이터센터','YIDO 데이터센터']),
                    ('유진투자증권','PF 주선사',ARRAY['유진투자증권']),
                    ('한국대체투자자산운용(KAAM)','자산운용사',ARRAY['한국대체투자자산운용','KAAM']),
                    ('OneAsia Network','글로벌 운영사',ARRAY['원아시아 데이터센터','OneAsia']),
                    ('Keppel','글로벌 투자·운영사',ARRAY['케펠 데이터센터','Keppel data center','Keppel data centre']),
                    ('Epoch Digital','개발·운영사',ARRAY['에포크 안양','Epoch Digital']),
                    ('Digital Edge','글로벌 운영사',ARRAY['Digital Edge','디지털엣지']),
                    ('Digital Realty','글로벌 운영사',ARRAY['Digital Realty','디지털리얼티']),
                    ('Equinix','글로벌 운영사',ARRAY['Equinix','에퀴닉스']),
                    ('DCI Data Centers','글로벌 운영사',ARRAY['DCI Data Centers','DCI 데이터센터','코람코·DCI']),
                    ('Empyrion Digital','글로벌 운영사',ARRAY['Empyrion Digital','엠피리온 디지털','엠피리온']),
                    ('Princeton Digital Group','글로벌 운영사',ARRAY['Princeton Digital Group','프린스턴 디지털','PDG']),
                    ('삼성물산','시공사·DBO',ARRAY['삼성물산']),
                    ('현대건설','시공사·DBO',ARRAY['현대건설']),
                    ('GS건설','시공사·DBO',ARRAY['GS건설']),
                    ('DL이앤씨','시공사·DBO',ARRAY['DL이앤씨','DL E&C']),
                    ('SK에코플랜트','시공사·DBO',ARRAY['SK에코플랜트'])
                ), matched AS (
                    SELECT p.player_name, p.player_type, ed.document_id,
                           ed.review_status, ed.published_at
                    FROM players p
                    LEFT JOIN evidence_document ed
                      ON ed.record_status='ACTIVE'
                     AND COALESCE(ed.published_at, ed.created_at)
                         >= CURRENT_DATE - INTERVAL '3 years'
                     AND EXISTS (
                         SELECT 1 FROM unnest(p.aliases) alias
                         WHERE ed.title ILIKE '%%' || alias || '%%'
                     )
                )
                SELECT player_name, player_type,
                       count(document_id) AS document_count,
                       count(document_id) FILTER (
                           WHERE review_status='CONFIRMED'
                       ) AS confirmed_document_count,
                       count(document_id) FILTER (
                           WHERE review_status<>'CONFIRMED'
                       ) AS candidate_document_count,
                       max(published_at) AS latest_published_at
                FROM matched
                GROUP BY player_name, player_type
                ORDER BY count(document_id) DESC, player_name
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
                  AND s.commercial_scope_status='IN_SCOPE'
                  AND s.commercial_review_status='CONFIRMED'
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

    def evidence_summary(self) -> dict[str, int]:
        with self.engine.connect() as connection:
            row = connection.execute(text("""
                SELECT count(*) AS total_document_count,
                       count(*) FILTER (WHERE ed.review_status='CONFIRMED') AS confirmed_document_count,
                       count(*) FILTER (WHERE ed.review_status='CONFIRMED' AND ed.access_scope='PUBLIC') AS public_document_count,
                       count(*) FILTER (WHERE ed.created_at>=CURRENT_TIMESTAMP-INTERVAL '7 days') AS recent_document_count,
                       count(DISTINCT ed.source_id) AS source_count
                FROM evidence_document ed
                WHERE ed.record_status='ACTIVE'
            """)).mappings().one()
        return {key: int(value or 0) for key, value in row.items()}

    def recent_evidence(self, limit: int = 24) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(text("""
                SELECT ed.title, ed.canonical_url, ed.publisher,
                       ed.published_at, ed.source_grade, sr.source_code
                FROM evidence_document ed
                JOIN source_registry sr ON sr.source_id=ed.source_id
                WHERE ed.record_status='ACTIVE' AND ed.access_scope='PUBLIC'
                  AND ed.review_status='CONFIRMED'
                ORDER BY COALESCE(ed.published_at,ed.created_at) DESC, ed.created_at DESC
                LIMIT :limit
            """), {"limit": limit}).mappings().all()
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
            if path == "/api/v1/evidence-summary":
                return json_response(start_response, "200 OK", repository.evidence_summary())
            if path == "/api/v1/recent-evidence":
                limit = parse_positive_int(query.get("limit", [None])[0], 24, 100)
                return json_response(start_response, "200 OK", {"items": repository.recent_evidence(limit)})
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
