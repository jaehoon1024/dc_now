#!/usr/bin/env python3
"""Generate a secret-free internal review and data-quality report."""
from __future__ import annotations
import argparse,json
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine,text
from src04_rss_collector import load_env_file,resolve_database_url

CHECKS={
 "site_quality":"""SELECT site_code AS code, concat_ws(', ',CASE WHEN geom IS NULL THEN '좌표 없음' END,CASE WHEN address_standard IS NULL THEN '표준주소 없음' END) AS issue FROM dc_site WHERE record_status='ACTIVE' AND (geom IS NULL OR address_standard IS NULL) ORDER BY site_code LIMIT 200""",
 "project_quality":"""SELECT project_code AS code, concat_ws(', ',CASE WHEN status_code IS NULL THEN '상태 없음' END,CASE WHEN planned_rfs_date IS NULL AND rfs_date IS NULL THEN '가동일 없음' END) AS issue FROM dc_project WHERE record_status='ACTIVE' AND (status_code IS NULL OR (planned_rfs_date IS NULL AND rfs_date IS NULL)) ORDER BY project_code LIMIT 200""",
 "relation_integrity":"""SELECT participation_id::text AS code,'참여 범위 참조 확인 필요' AS issue FROM company_participation cp WHERE (scope_type='SITE' AND NOT EXISTS(SELECT 1 FROM dc_site s WHERE s.site_id=cp.scope_id)) OR (scope_type='PROJECT' AND NOT EXISTS(SELECT 1 FROM dc_project p WHERE p.project_id=cp.scope_id)) OR (scope_type='PHASE' AND NOT EXISTS(SELECT 1 FROM project_phase p WHERE p.phase_id=cp.scope_id)) LIMIT 200""",
 "capacity_quality":"""SELECT capacity_id::text AS code,concat_ws(', ',CASE WHEN normalized_value IS NULL AND normalized_value_mw IS NULL THEN '정규화값 없음' END,CASE WHEN document_url IS NULL AND evidence_location IS NULL THEN '근거 없음' END) AS issue FROM capacity_snapshot WHERE review_status IN('CANDIDATE','CONFIRMED') AND ((normalized_value IS NULL AND normalized_value_mw IS NULL) OR (document_url IS NULL AND evidence_location IS NULL)) LIMIT 200""",
 "evidence_freshness":"""SELECT document_id::text AS code,CASE WHEN canonical_url IS NULL THEN 'URL 없음' ELSE '365일 초과' END AS issue FROM evidence_document WHERE record_status='ACTIVE' AND (canonical_url IS NULL OR COALESCE(published_at,created_at)<CURRENT_TIMESTAMP-INTERVAL '365 days') LIMIT 200""",
}
QUEUE_TABLES={"site":"dc_site","project":"dc_project","company":"company","participation":"company_participation","capacity":"capacity_snapshot","evidence":"evidence_document","fact":"extracted_fact"}

def build_report(engine):
 result={"generated_at":datetime.now().astimezone().isoformat(),"checks":{},"review_queue":{}}
 with engine.connect() as c:
  for name,query in CHECKS.items():result["checks"][name]=[dict(r) for r in c.execute(text(query)).mappings()]
  for name,table in QUEUE_TABLES.items():
   result["review_queue"][name]=c.execute(text(f"SELECT count(*) FROM {table} WHERE review_status IN ('CANDIDATE','NEEDS_EVIDENCE','CONFLICT')")).scalar_one()
 return result

def render_html(report):
 import html
 esc=lambda x:html.escape(str(x))
 cards=''.join(f'<div><b>{esc(k)}</b><strong>{v}</strong></div>' for k,v in report['review_queue'].items())
 sections=[]
 for name,rows in report['checks'].items():
  body=''.join(f'<tr><td>{esc(r["code"])}</td><td>{esc(r["issue"])}</td></tr>' for r in rows) or '<tr><td colspan="2">문제 없음</td></tr>'
  sections.append(f'<section><h2>{esc(name)} ({len(rows)})</h2><table><tr><th>코드</th><th>점검 결과</th></tr>{body}</table></section>')
 return f'''<!doctype html><html lang="ko"><meta charset="utf-8"><title>데이터 품질·검토 현황</title><style>body{{font:14px system-ui;margin:30px;background:#f2f5f8;color:#18304a}}.cards{{display:grid;grid-template-columns:repeat(7,1fr);gap:10px}}.cards div,section{{background:white;border:1px solid #d8e1ea;border-radius:10px;padding:15px;margin:12px 0}}strong{{display:block;font-size:25px}}table{{border-collapse:collapse;width:100%}}td,th{{padding:8px;border-bottom:1px solid #ddd;text-align:left}}@media(max-width:900px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}</style><h1>데이터 품질·검토 현황</h1><p>생성: {esc(report['generated_at'])}</p><div class="cards">{cards}</div>{''.join(sections)}</html>'''

def main():
 p=argparse.ArgumentParser();p.add_argument("--json",type=Path);p.add_argument("--html",type=Path);a=p.parse_args();load_env_file();e=create_engine(resolve_database_url(),connect_args={"options":"-c default_transaction_read_only=on -c statement_timeout=10000"})
 try:r=build_report(e)
 finally:e.dispose()
 if a.json:a.json.parent.mkdir(parents=True,exist_ok=True);a.json.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
 if a.html:a.html.parent.mkdir(parents=True,exist_ok=True);a.html.write_text(render_html(r),encoding="utf-8")
 if not a.json and not a.html:print(json.dumps(r,ensure_ascii=False,indent=2))
 return 0
if __name__=="__main__":raise SystemExit(main())
