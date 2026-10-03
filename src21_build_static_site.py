#!/usr/bin/env python3
"""Build the static dashboard snapshot used by GitHub Pages and local previews."""
from __future__ import annotations
import html,json,shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from public_api import PublicRepository,json_value
from src04_rss_collector import load_env_file,resolve_database_url
ROOT=Path(__file__).resolve().parent;OUT=ROOT/"deploy"
def build_payload(repo):
 public_sites,total=repo.sites(None,None,500,0)
 sites=repo.tracking_sites()
 details={x["site_code"]:repo.site_detail(x["site_code"]) for x in public_sites}
 return {"generated_at":datetime.now().astimezone().isoformat(),"total":len(sites),"public_total":total,"target_summary":repo.target_summary(),"sites":sites,"details":details,"regions":repo.regions(),"companies":repo.companies(),"yearly":repo.yearly(),"collection_status":repo.collection_status(),"evidence_summary":repo.evidence_summary(),"recent_evidence":repo.recent_evidence()}
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
def render_v2(payload):
 page=(ROOT/"dashboard/professional_v3.html").read_text(encoding="utf-8")
 sites=payload["sites"]
 def has_coordinate(x):return x.get("latitude") is not None and x.get("longitude") is not None
 def has_stage(x):return bool(x.get("lifecycle_group")) and x.get("lifecycle_group")!="UNKNOWN"
 def has_operator(x):return bool(str(x.get("operator_names") or "").strip())
 def has_capacity(x):return any(x.get(k) is not None for k in ("operating_grid_intake_mw","operating_it_load_mw","development_grid_intake_mw","development_it_load_mw"))
 def has_address(x):return x.get("location_precision") in {"ROOFTOP","ROAD","PARCEL"}
 def has_rfs(x):return bool(x.get("earliest_rfs_date"))
 def gap_labels(x):
  result=[]
  if x.get("public_visible") and x.get("review_status")=="CONFIRMED":result.append(("base","공개 확정"))
  elif x.get("review_status")!="CONFIRMED":result.append(("","근거 확인 필요"))
  if not has_coordinate(x):result.append(("","좌표 확인 필요"))
  if not has_stage(x):result.append(("","운영 단계 확인 필요"))
  if not has_operator(x):result.append(("","운영사 확인 필요"))
  if not has_address(x):result.append(("","상세 주소 확인 필요"))
  if not has_capacity(x):result.append(("","용량 확인 필요"))
  if not has_rfs(x):result.append(("","RFS 확인 필요"))
  if x.get("discovery_target") or "수집 검증 대상" in str(x.get("site_name") or ""):result.append(("","수집 검증 대상"))
  return result
 stage_label={"OPERATING":"운영 중","DEVELOPMENT":"개발 중","MIXED":"운영·개발 병행","ON_HOLD":"보류","UNKNOWN":"미확인"}
 def gaps_html(x):return '<div class="flags">'+''.join(f'<span class="flag {"ok" if kind=="base" else ""}">{html.escape(label)}</span>' for kind,label in gap_labels(x))+'</div>'
 rows="".join(
  "<tr data-code=\"{}\"><td><input class=\"comparecheck\" type=\"checkbox\" data-code=\"{}\"></td><td class=\"sitecell\"><b>{}</b><small>{}</small></td><td>{} {}</td><td><span class=\"status {}\">{}</span></td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
   html.escape(str(x.get("site_code") or "")),html.escape(str(x.get("site_code") or "")),html.escape(str(x.get("site_name") or "—")),html.escape(str(x.get("site_code") or "—")),html.escape(str(x.get("sido") or "—")),html.escape(str(x.get("sigungu") or "")),str(x.get("lifecycle_group") or "UNKNOWN").lower().replace("_","-"),html.escape(stage_label.get(x.get("lifecycle_group"),str(x.get("lifecycle_group") or "미확인"))),html.escape(str(x.get("operator_names") or "미확인")),html.escape(str(x.get("operating_grid_intake_mw") or x.get("development_grid_intake_mw") or "미확인")),html.escape(str(x.get("operating_it_load_mw") or x.get("development_it_load_mw") or "미확인")),html.escape(str(x.get("earliest_rfs_date") or "미확인")),gaps_html(x),
  ) for x in sites
 )
 target=payload.get("target_summary") or {"target_total":payload["total"],"public_total":payload["total"],"needs_evidence_total":0}
 total=len(sites)
 counts={"coordinate":sum(map(has_coordinate,sites)),"stage":sum(map(has_stage,sites)),"operator":sum(map(has_operator,sites)),"capacity":sum(map(has_capacity,sites)),"address":sum(map(has_address,sites)),"rfs":sum(map(has_rfs,sites))}
 score=round(sum(counts.values())/(total*6)*100) if total else 0
 operating_sites=[x for x in sites if x.get("lifecycle_group")=="OPERATING"]
 development_sites=[x for x in sites if x.get("lifecycle_group")=="DEVELOPMENT"]
 mixed_sites=[x for x in sites if x.get("lifecycle_group")=="MIXED"]
 operating_it_known=[x for x in operating_sites if x.get("operating_it_load_mw") is not None]
 operating_it=sum(float(x.get("operating_it_load_mw") or 0) for x in operating_sites)
 grid_known=[x for x in sites if x.get("operating_grid_intake_mw") is not None or x.get("development_grid_intake_mw") is not None]
 grid=sum(float(x.get("operating_grid_intake_mw") or x.get("development_grid_intake_mw") or 0) for x in sites)
 development_it_known=[x for x in development_sites if x.get("development_it_load_mw") is not None]
 development_it=sum(float(x.get("development_it_load_mw") or 0) for x in development_sites)
 evidence_summary=payload.get("evidence_summary") or {}
 collection_healthy=bool(payload.get("collection_status")) and all(x.get("run_status")=="SUCCESS" for x in payload.get("collection_status",[]))
 evidence_rows="".join(
  '<a class="evidenceitem" target="_blank" rel="noopener" href="{}"><span class="grade">{}</span><span><b>{}</b><small>{} · {}</small></span></a>'.format(
   html.escape(str(x.get("canonical_url") or "#")),html.escape(str(x.get("source_grade") or "—")),html.escape(str(x.get("title") or "제목 없음")),html.escape(str(x.get("publisher") or x.get("source_code") or "출처 미확인")),html.escape(str(x.get("published_at") or "")[:10]),
 ) for x in payload.get("recent_evidence",[])
 )
 completeness=''.join('<div class="comprow"><span>{}</span><div class="track"><i style="width:{}%"></i></div><b>{} · {}%</b></div>'.format(label,round(counts[key]/total*100) if total else 0,counts[key],round(counts[key]/total*100) if total else 0) for key,label in (("coordinate","좌표"),("stage","운영 단계"),("operator","운영사"),("address","상세 주소"),("capacity","용량"),("rfs","RFS")))
 replacements={
  '데이터 준비 중':f'기준 {html.escape(str(payload.get("generated_at") or "미확인"))[:16].replace("T"," ")}',
  '<span class="health" id="systemStatus"><i></i>수집 상태 확인 중</span>':f'<span class="health" id="systemStatus"><i></i>{"수집 시스템 정상" if collection_healthy else "수집 상태 점검 필요"}</span>',
  '<strong id="total">0</strong>':f'<strong id="total">{target["target_total"]}</strong>',
  '<small id="targetBreakdown">센터 원장 집계</small>':f'<small id="targetBreakdown">공개 승인 {target["public_total"]} · 좌표 확인 {counts["coordinate"]}</small>',
  '<span id="asOf">—</span>':f'<span id="asOf">{html.escape(str(payload.get("generated_at") or "")[:10])}</span>',
  '<strong id="operatingCount">0</strong>':f'<strong id="operatingCount">{len(operating_sites)}</strong>',
  '<strong id="developmentCount">0</strong>':f'<strong id="developmentCount">{len(development_sites)}</strong>',
  '<strong id="mixedCount">0</strong>':f'<strong id="mixedCount">{len(mixed_sites)}</strong>',
  '<strong id="operatingIt">미확인</strong>':f'<strong id="operatingIt">{operating_it:g} MW</strong>' if operating_it_known else '<strong id="operatingIt">미확인</strong>',
  '<small id="operatingItCoverage">확보율 0%</small>':f'<small id="operatingItCoverage">확보 {len(operating_it_known)}/{len(operating_sites)}개 운영센터</small>',
  '<strong id="gridCapacity">미확인</strong>':f'<strong id="gridCapacity">{grid:g} MW</strong>' if grid_known else '<strong id="gridCapacity">미확인</strong>',
  '<small id="gridCoverage">확보율 0%</small>':f'<small id="gridCoverage">확보 {len(grid_known)}/{total}개 센터</small>',
  '<strong id="developmentIt">미확인</strong>':f'<strong id="developmentIt">{development_it:g} MW</strong>' if development_it_known else '<strong id="developmentIt">미확인</strong>',
  '<small id="developmentCoverage">확보율 0%</small>':f'<small id="developmentCoverage">확보 {len(development_it_known)}/{len(development_sites)}개 개발센터</small>',
  '<strong id="rfsCount">0</strong>':f'<strong id="rfsCount">{counts["rfs"]}</strong>',
  '<small id="rfsCoverage">RFS 확보율 0%</small>':f'<small id="rfsCoverage">RFS 확보 {counts["rfs"]}/{total}개 센터</small>',
  '핵심 용량 정보의 확보율을 계산 중입니다.':f'수전용량은 {len(grid_known)}/{total}개 센터에서 {grid:g} MW가 확인됐습니다. IT Load·RFS·GPU/DLC·Available Capacity는 추가 확보가 필요합니다.',
  '<strong id="coordinateCount">0</strong>':f'<strong id="coordinateCount">{counts["coordinate"]}</strong>',
  '<span class="delta" id="coordinateRate">0%</span>':f'<span class="delta" id="coordinateRate">{round(counts["coordinate"]/total*100) if total else 0}%</span>',
  '<strong id="stageCount">0</strong>':f'<strong id="stageCount">{counts["stage"]}</strong>',
  '<span class="delta" id="stageRate">0%</span>':f'<span class="delta" id="stageRate">{round(counts["stage"]/total*100) if total else 0}%</span>',
  '<strong id="operatorCount">0</strong>':f'<strong id="operatorCount">{counts["operator"]}</strong>',
  '<span class="delta" id="operatorRate">0%</span>':f'<span class="delta" id="operatorRate">{round(counts["operator"]/total*100) if total else 0}%</span>',
  '<strong id="capacityCount">0</strong>':f'<strong id="capacityCount">{counts["capacity"]}</strong>',
  '<span class="delta" id="capacityRate">0%</span>':f'<span class="delta" id="capacityRate">{round(counts["capacity"]/total*100) if total else 0}%</span>',
  '<strong id="evidenceTotal">0</strong>':f'<strong id="evidenceTotal">{evidence_summary.get("confirmed_document_count",0)}</strong>',
  '<span class="delta" id="sourceCount">0 sources</span>':f'<span class="delta" id="sourceCount">{evidence_summary.get("source_count",0)} sources</span>',
  '<strong id="qualityScore">0%</strong>':f'<strong id="qualityScore">{score}%</strong>',
  '<strong class="qualityscore" id="qualityScore">0%</strong>':f'<strong class="qualityscore" id="qualityScore">{score}%</strong>',
  '<strong id="needCoordinate">0</strong>':f'<strong id="needCoordinate">{total-counts["coordinate"]}</strong>',
  '<strong id="needStage">0</strong>':f'<strong id="needStage">{total-counts["stage"]}</strong>',
  '<strong id="needOperator">0</strong>':f'<strong id="needOperator">{total-counts["operator"]}</strong>',
  '<strong id="needAddress">0</strong>':f'<strong id="needAddress">{total-counts["address"]}</strong>',
  '<strong id="needCapacity">0</strong>':f'<strong id="needCapacity">{total-counts["capacity"]}</strong>',
  '<strong id="needRfs">0</strong>':f'<strong id="needRfs">{total-counts["rfs"]}</strong>',
  '<span id="approvedCount">0</span>':f'<span id="approvedCount">{target["public_total"]}</span>',
  '<b id="needCoordinate">0</b>':f'<b id="needCoordinate">{total-counts["coordinate"]}</b>',
  '<b id="needStage">0</b>':f'<b id="needStage">{total-counts["stage"]}</b>',
  '<b id="needOperator">0</b>':f'<b id="needOperator">{total-counts["operator"]}</b>',
  '<b id="needAddress">0</b>':f'<b id="needAddress">{total-counts["address"]}</b>',
  '<b id="needCapacity">0</b>':f'<b id="needCapacity">{total-counts["capacity"]}</b>',
  '<b id="needRfs">0</b>':f'<b id="needRfs">{total-counts["rfs"]}</b>',
  '<b id="approvedCount">0</b>':f'<b id="approvedCount">{target["public_total"]}</b>',
  '<span class="count" id="resultcount">0건</span>':f'<span class="count" id="resultcount">{len(sites)}건</span>',
  '<tbody id="rows"></tbody>':f'<tbody id="rows">{rows}</tbody>',
  '<div class="chartbody" id="completeness"></div>':f'<div class="chartbody" id="completeness">{completeness}</div>',
  '<span class="tag" id="evidenceSummary">근거 집계 중</span>':f'<span class="tag" id="evidenceSummary">근거 {evidence_summary.get("total_document_count",0)}건 · 공개 {evidence_summary.get("public_document_count",0)}건 · 소스 {evidence_summary.get("source_count",0)}개</span>',
  '<div class="evidencelist" id="evidence"><div class="empty">수집 근거를 불러오는 중입니다.</div></div>':f'<div class="evidencelist" id="evidence">{evidence_rows}</div>',
 }
 if sites:replacements['<div class="empty" id="empty">']='<div class="empty" id="empty" hidden>'
 for old,new in replacements.items():page=page.replace(old,new)
 return page
def write_site(payload,out=OUT):
 out.mkdir(parents=True,exist_ok=True);(out/"index.html").write_text(render_v2(payload),encoding="utf-8")
 (out/"data.json").write_text(json.dumps(payload,ensure_ascii=False,default=json_value,separators=(",",":")),encoding="utf-8")
 (out/".nojekyll").touch()
 for name in ("app_v3.css","app_v3.js"):
  shutil.copyfile(ROOT/"dashboard"/name,out/name)
 (out/"_headers").write_text("/*\n  Cache-Control: public, max-age=0, must-revalidate\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n  Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src https://www.google.com https://maps.google.com\n\n/data.json\n  Cache-Control: public, max-age=60, must-revalidate\n",encoding="utf-8")
def main():
 load_env_file();e=create_engine(resolve_database_url(),connect_args={"options":"-c default_transaction_read_only=on -c statement_timeout=10000"})
 try:payload=build_payload(PublicRepository(e))
 finally:e.dispose()
 write_site(payload);print(f"정적 사이트 생성: {OUT} / 추적 대상 {payload['total']}건 / 공개 확정 {payload['public_total']}건");return 0
if __name__=="__main__":raise SystemExit(main())
