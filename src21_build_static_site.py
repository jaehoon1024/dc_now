#!/usr/bin/env python3
"""Build a Netlify-ready snapshot containing approved public data only."""
from __future__ import annotations
import html,json
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine
from public_api import PublicRepository,json_value
from src04_rss_collector import load_env_file,resolve_database_url
ROOT=Path(__file__).resolve().parent;OUT=ROOT/"deploy"
def build_payload(repo):
 sites,total=repo.sites(None,None,500,0)
 details={x["site_code"]:repo.site_detail(x["site_code"]) for x in sites}
 return {"generated_at":datetime.now().astimezone().isoformat(),"total":total,"sites":sites,"details":details,"regions":repo.regions(),"companies":repo.companies(),"yearly":repo.yearly(),"collection_status":repo.collection_status()}
def render_html(payload):
 page=(ROOT/"dashboard/professional.html").read_text(encoding="utf-8")
 sites=payload["sites"]
 rows="".join(
  "<tr data-code=\"{}\"><td><b>{}</b><br><small>{}</small></td><td>{} {}</td><td><span class=\"badge\">{}</span></td><td>{}</td><td>{}</td><td>{}</td><td><a target=\"_blank\" rel=\"noopener\" href=\"https://www.google.com/maps/search/?api=1&amp;query={},{}\">지도 ↗</a></td></tr>".format(
   html.escape(str(x.get("site_code") or "")),
   html.escape(str(x.get("site_name") or "—")),
   html.escape(str(x.get("operator_names") or "운영사 미확인")),
   html.escape(str(x.get("sido") or "—")),
   html.escape(str(x.get("sigungu") or "—")),
   html.escape(str(x.get("lifecycle_group") or "—")),
   html.escape(str(x.get("operating_grid_intake_mw") or "미공개")),
   html.escape(str(x.get("operating_it_load_mw") or "—")),
   html.escape(str(x.get("latest_data_update") or "")[:10]),
   html.escape(str(x.get("latitude") or "")),
   html.escape(str(x.get("longitude") or "")),
  ) for x in sites
 )
 replacements={
  '<div id="generated">승인된 공개 데이터</div>':f'<div id="generated">생성 {html.escape(str(payload.get("generated_at") or "미확인"))}</div>',
  '<strong id="total">0</strong>':f'<strong id="total">{payload["total"]}</strong>',
  '<strong id="op">0</strong>':f'<strong id="op">{sum(x.get("lifecycle_group") in {"OPERATING","MIXED"} for x in sites)}</strong>',
  '<strong id="dev">0</strong>':f'<strong id="dev">{sum(x.get("lifecycle_group") in {"DEVELOPMENT","MIXED"} for x in sites)}</strong>',
  '<strong id="docs">0</strong>':f'<strong id="docs">{sum(x.get("new_document_count") or 0 for x in payload["collection_status"])}</strong>',
  '<tbody id="rows"></tbody>':f'<tbody id="rows">{rows}</tbody>',
 }
 if sites:replacements['<div class="empty" id="empty">']='<div class="empty" id="empty" hidden>'
 for old,new in replacements.items():page=page.replace(old,new)
 return page
def write_site(payload,out=OUT):
 out.mkdir(parents=True,exist_ok=True);(out/"index.html").write_text(render_html(payload),encoding="utf-8")
 (out/"data.json").write_text(json.dumps(payload,ensure_ascii=False,default=json_value,separators=(",",":")),encoding="utf-8")
 (out/"_headers").write_text("/*\n  Cache-Control: public, max-age=0, must-revalidate\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n  Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'\n\n/data.json\n  Cache-Control: public, max-age=60, must-revalidate\n",encoding="utf-8")
def main():
 load_env_file();e=create_engine(resolve_database_url(),connect_args={"options":"-c default_transaction_read_only=on -c statement_timeout=10000"})
 try:payload=build_payload(PublicRepository(e))
 finally:e.dispose()
 write_site(payload);print(f"정적 사이트 생성: {OUT} / 공개 센터 {payload['total']}건");return 0
if __name__=="__main__":raise SystemExit(main())
