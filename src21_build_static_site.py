#!/usr/bin/env python3
"""Build a Netlify-ready snapshot containing approved public data only."""
from __future__ import annotations
import html,json
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from public_api import PublicRepository,json_value
from src04_rss_collector import load_env_file,resolve_database_url
ROOT=Path(__file__).resolve().parent;OUT=ROOT/"deploy"
def build_payload(repo):
 sites,total=repo.sites(None,None,500,0)
 details={x["site_code"]:repo.site_detail(x["site_code"]) for x in sites}
 return {"generated_at":datetime.now().astimezone().isoformat(),"total":total,"target_summary":repo.target_summary(),"sites":sites,"details":details,"regions":repo.regions(),"companies":repo.companies(),"yearly":repo.yearly(),"collection_status":repo.collection_status()}
def render_html(payload):
 page=(ROOT/"dashboard/professional.html").read_text(encoding="utf-8")
 page=page.replace(
  '.map{height:430px;position:relative;overflow:hidden;background:linear-gradient(145deg,#eaf2f7,#dcebf0)}',
  '.map{height:430px;position:relative;overflow:hidden;background:#eaf2f7}.map iframe{width:100%;height:100%;border:0}.maphint{position:absolute;left:12px;bottom:12px;background:#081a2bdd;color:#fff;padding:8px 10px;border-radius:6px;font-size:11px;pointer-events:none}',
 )
 page=page.replace(
  '<h2>전국 데이터센터 자산 지도</h2><span class="meta">운영·개발 단계별 위치</span></div><div class="map" id="map"><div class="grid"></div><div class="land"></div><div class="legend"><i style="background:var(--green)"></i>운영 <i style="background:var(--amber)"></i>개발·기타</div></div>',
  '<h2>Google Maps · 데이터센터 자산 지도</h2><span class="meta">표준주소 기준 · 센터 행을 선택하면 이동</span></div><div class="map" id="map"><iframe id="gmap" title="Google 데이터센터 지도" loading="lazy" referrerpolicy="no-referrer-when-downgrade" src="https://maps.google.com/maps?q=36.3%2C127.8&amp;z=7&amp;output=embed"></iframe><div class="maphint" id="maphint">센터 목록에서 행을 선택하세요</div></div>',
 )
 page=page.replace(
  "function detail(code){let x=D.details[code]||D.sites.find(v=>v.site_code===code);$('#dtitle').textContent=x.site_name;",
  "function detail(code){let x=D.details[code]||D.sites.find(v=>v.site_code===code);let loc=x.address_standard||((x.latitude!=null&&x.longitude!=null)?x.latitude+','+x.longitude:'');if(loc){$('#gmap').src=`https://maps.google.com/maps?q=${encodeURIComponent(loc)}&z=16&output=embed`;$('#maphint').textContent=x.site_name+' · '+loc}$('#dtitle').textContent=x.site_name;",
 )
 page=page.replace(
  ";document.querySelectorAll('.marker').forEach(x=>x.remove());F.filter(x=>x.latitude!=null&&x.longitude!=null).forEach(x=>{let m=document.createElement('button');m.className='marker '+x.lifecycle_group;m.title=x.site_name;m.style.left=((x.longitude-124)/8*64+18)+'%';m.style.top=((39-x.latitude)/6*84+8)+'%';m.onclick=()=>detail(x.site_code);$('#map').append(m)});document.querySelectorAll('#rows tr').forEach(x=>x.onclick=e=>{if(e.target.tagName!=='A')detail(x.dataset.code)});bars()}",
  ";document.querySelectorAll('#rows tr').forEach(x=>x.onclick=e=>{if(e.target.tagName!=='A')detail(x.dataset.code)});bars()}",
 )
 page=page.replace(
  '<dt>운영사</dt><dd>${esc(x.operator_names)}</dd>',
  '<dt>운영사</dt><dd>${esc(x.operator_names)}</dd><dt>자산운용사</dt><dd>${esc(x.asset_manager_names)}</dd><dt>시공사</dt><dd>${esc(x.builder_names)}</dd>',
 )
 page=page.replace('공개·검토 완료 기준','수집 대상 총계 · 공개 지표 분리')
 page=page.replace(
  '<div class="foot">',
  '<section class="panel section"><div class="ph"><h2>생태계 추적 범위</h2><span class="meta">근거 확인 후 센터·프로젝트와 연결</span></div><div class="body"><div class="metric"><span>자산운용사</span><b>이지스 · 코람코 · ESR켄달스퀘어 · 마스턴</b></div><div class="metric"><span>시공사</span><b>삼성물산 · 현대건설 · GS건설 · DL이앤씨 · SK에코플랜트</b></div></div></section><div class="foot">',
 )
 sites=payload["sites"]
 rows="".join(
  "<tr data-code=\"{}\"><td><b>{}</b><br><small>{}</small></td><td>{} {}</td><td><span class=\"badge\">{}</span></td><td>{}</td><td>{}</td><td>{}</td><td><a target=\"_blank\" rel=\"noopener\" href=\"https://www.google.com/maps/search/?api=1&amp;query={}\">지도 ↗</a></td></tr>".format(
   html.escape(str(x.get("site_code") or "")),
   html.escape(str(x.get("site_name") or "—")),
   html.escape(str(x.get("operator_names") or "운영사 미확인")),
   html.escape(str(x.get("sido") or "—")),
   html.escape(str(x.get("sigungu") or "—")),
   html.escape(str(x.get("lifecycle_group") or "—")),
   html.escape(str(x.get("operating_grid_intake_mw") or "미공개")),
   html.escape(str(x.get("operating_it_load_mw") or "—")),
   html.escape(str(x.get("latest_data_update") or "")[:10]),
   html.escape(quote_plus(str(x.get("address_standard") or x.get("site_name") or ""))),
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
 target=payload.get("target_summary") or {"target_total":payload["total"],"public_total":payload["total"],"needs_evidence_total":0}
 replacements['<small>공개 센터</small>']=f'<small>공개 {target["public_total"]} / 근거 검토 {target["needs_evidence_total"]}</small>'
 replacements[f'<strong id="total">{payload["total"]}</strong>']=f'<strong id="total">{target["target_total"]}</strong>'
 if sites:replacements['<div class="empty" id="empty">']='<div class="empty" id="empty" hidden>'
 for old,new in replacements.items():page=page.replace(old,new)
 page=page.replace("$('#total').textContent=F.length;", "")
 return page
def write_site(payload,out=OUT):
 out.mkdir(parents=True,exist_ok=True);(out/"index.html").write_text(render_html(payload),encoding="utf-8")
 (out/"data.json").write_text(json.dumps(payload,ensure_ascii=False,default=json_value,separators=(",",":")),encoding="utf-8")
 (out/"_headers").write_text("/*\n  Cache-Control: public, max-age=0, must-revalidate\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n  Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src https://www.google.com https://maps.google.com\n\n/data.json\n  Cache-Control: public, max-age=60, must-revalidate\n",encoding="utf-8")
def main():
 load_env_file();e=create_engine(resolve_database_url(),connect_args={"options":"-c default_transaction_read_only=on -c statement_timeout=10000"})
 try:payload=build_payload(PublicRepository(e))
 finally:e.dispose()
 write_site(payload);print(f"정적 사이트 생성: {OUT} / 공개 센터 {payload['total']}건");return 0
if __name__=="__main__":raise SystemExit(main())
