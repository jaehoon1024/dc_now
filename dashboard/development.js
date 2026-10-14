(function(root){
 'use strict';
 const $=s=>document.querySelector(s);
 const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const num=x=>x!==null&&x!==undefined&&Number.isFinite(Number(x))?Number(x).toLocaleString('ko-KR',{maximumFractionDigits:1}):'—';
 const urls=x=>{try{const u=new URL(x);return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password?u.href:'';}catch{return '';}};
 const labels={ADDRESS_MATCH:'주소 일치',NAME_HINT:'이름 대조 필요',AMBIGUOUS_ADDRESS:'동일 주소 복수 센터',UNLINKED:'원장 연결 필요'};
 const capTypes={GRID_INTAKE_MW:'수전',IT_LOAD_MW:'IT',ANNOUNCED_UNCLASSIFIED_MW:'발표 · 기준 미확인'};
 const region=x=>String(x||'').replace(/특별자치도|특별자치시|특별시|광역시/g,'').replace('경기도','경기').replace('강원도','강원').replace('전라북도','전북').replace('전라남도','전남').replace('충청남도','충남').replace('충청북도','충북').replace('경상남도','경남').replace('경상북도','경북');
 const date=x=>x?String(x).slice(0,10):'—';
 const stageLabel=x=>x==='준공'?'사용승인':x||'미확인';
 const csvCell=x=>'"'+String(x??'').replace(/^[\s]*[=+@-]/,"'$&").replace(/"/g,'""')+'"';
 class DCDevelopment{
  constructor({onCenter=()=>{},onAddress=()=>{}}={}){
   this.onCenter=onCenter;this.onAddress=onAddress;this.filter={stage:'',connection:'',year:null,page:0};this.rows=[];this.notes={};this.energyAll=false;
   try{const n=JSON.parse(localStorage.getItem('dc-now-permit-notes-v1')||'{}');if(n&&typeof n==='object'&&!Array.isArray(n))this.notes=n;}catch{}
   this.wire();
  }
  reset(){
   Object.assign(this.filter,{stage:'',connection:'',year:null,page:0});
   this.energyAll=false;
   $('#permitConnection').value='';
  }
  wire(){
   document.querySelectorAll('[data-permit-stage]').forEach(b=>b.addEventListener('click',()=>{this.filter.stage=b.dataset.permitStage;this.filter.page=0;this.filter.year=null;this.render();}));
   $('#permitConnection').addEventListener('change',e=>{this.filter.connection=e.target.value;this.filter.page=0;this.render();});
   $('#permitPrev').addEventListener('click',()=>{this.filter.page--;this.table();});$('#permitNext').addEventListener('click',()=>{this.filter.page++;this.table();});
   $('#permitExport').addEventListener('click',()=>this.export());
   $('#permits').addEventListener('click',e=>{
    const permit=e.target.closest('[data-permit-id]');if(permit)this.detail(permit.dataset.permitId);
    const action=e.target.closest('[data-connection-action]');if(action){this.filter.connection=action.dataset.connectionAction;$('#permitConnection').value=this.filter.connection;this.filter.page=0;this.render();}
    const year=e.target.closest('[data-permit-year]');if(year){this.filter.year=this.filter.year===year.dataset.permitYear?null:year.dataset.permitYear;this.filter.page=0;this.render();}
   });
   $('#energyPanel').addEventListener('click',e=>{if(e.target.closest('#energyToggle')){this.energyAll=!this.energyAll;this.energy();}});
   const dialog=document.createElement('dialog');dialog.id='permitDialog';dialog.className='detail-dialog';dialog.setAttribute('aria-labelledby','permitTitle');
   dialog.innerHTML='<div class="drawer-head"><div><small>PERMIT / DEVELOPMENT EVIDENCE</small><h2 id="permitTitle"></h2><div id="permitDetailMeta"></div></div><button id="closePermit" class="close-button" aria-label="인허가 상세 닫기">×</button></div><div id="permitBody" class="drawer-body"></div><div class="drawer-foot"><span>건축 사용승인과 서비스 RFS는 별도입니다.</span><a id="permitSource" class="primary-link" target="_blank" rel="noopener">참고 출처 ↗</a></div>';
   document.body.append(dialog);$('#closePermit').addEventListener('click',()=>dialog.close());
   dialog.addEventListener('click',e=>{const center=e.target.closest('[data-master-site]');if(center){dialog.close();this.onCenter(center.dataset.masterSite);}const map=e.target.closest('[data-permit-map]');if(map){dialog.close();this.onAddress(this.selected.address,this.selected.building_name);}});
   dialog.addEventListener('submit',e=>{if(e.target.id!=='permitNoteForm')return;e.preventDefault();const note=$('#permitNote').value.trim();this.notes[this.selected.candidate_id]=note;try{localStorage.setItem('dc-now-permit-notes-v1',JSON.stringify(this.notes));$('#permitNoteStatus').textContent='내 브라우저 검토메모 저장 완료';}catch{$('#permitNoteStatus').textContent='저장 공간에 기록하지 못했습니다. 메모를 별도로 보관하세요.';}});
  }
  update(data,filters){
   this.dataset=data.development_intelligence;
   this.global={region:filters.region,q:filters.q};
   const key=JSON.stringify(this.global);if(this.globalKey!==key){this.filter.page=0;this.filter.year=null;this.globalKey=key;}
   this.render();
  }
  render(){
   const d=this.dataset;$('#permits').hidden=!d;$('#discoveryRibbon').hidden=!d;$('#energyPanel').hidden=!d;
   if(!d)return;
   const summary=d.summary||{},bad=d.collection?.status!=='SUCCESS',age=Date.now()-Date.parse(d.collection?.last_success_at||''),stale=!bad&&(!Number.isFinite(age)||age>36*3600000);
   $('#discoveryRibbon').innerHTML=`<a href="#permits">인허가 <b>${num(summary.permit_records)}</b>건 · 대지 식별자 <b>${num(summary.parcel_groups)}</b>종</a><span>원장 주소 연결 ${num(summary.address_matched_records)}건 / ${num(summary.linked_master_sites)}센터 · 연결 필요 ${num(summary.unlinked_records)}건</span><span class="chip ${bad?'bad':stale?'dev':'op'}">${bad?'최근 수집 실패 · 이전 자료 유지':stale?'수집 시각 확인 필요':'참고 데이터 갱신'}</span>`;
   $('#permitMeta').innerHTML=`<span>인허가 기준 ${esc(date(d.permits_updated_on))} · 참고 자료 생성 ${esc(d.source_built_raw||'미확인')} · 수집 ${esc(d.collection?.last_success_at?new Date(d.collection.last_success_at).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false}):'미확인')} KST</span><span>참고 출처 <a href="${esc(urls(d.source_url))}" target="_blank" rel="noopener">NamePF ↗</a> · 원출처 <a href="${esc(urls(d.primary_source_url))}" target="_blank" rel="noopener">건축HUB ↗</a></span>${bad?'<strong>마지막 성공 자료를 표시 중입니다. 원출처 갱신을 확인해야 합니다.</strong>':''}`;
   const q=String(this.global?.q||'').toLowerCase().trim(),r=region(this.global?.region);
   this.base=(d.items||[]).filter(x=>(!r||x.canonical_region===r||x.canonical_region==='전남광주'&&['전남','광주'].includes(r))&&(!q||[x.building_name,x.address,x.region,x.district,...(x.connection?.candidates||[]).map(s=>s.site_name),...(x.news||[]).map(n=>n.title)].join(' ').toLowerCase().includes(q)));
   this.rows=this.base.filter(x=>(!this.filter.stage||x.permit_stage===this.filter.stage)&&(!this.filter.connection||x.connection?.status===this.filter.connection)&&(!this.filter.year||String(x.dates?.permit_on||'').startsWith(this.filter.year))).sort((a,b)=>String(b.dates?.permit_on||'').localeCompare(String(a.dates?.permit_on||'')));
   const stages=['착공 전','공사 중','준공'];
   document.querySelectorAll('[data-permit-stage]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.permitStage===this.filter.stage)));
   $('#permitMetrics').innerHTML=[...stages.map(s=>({label:stageLabel(s),value:this.base.filter(x=>x.permit_stage===s).length,unit:'건',note:s==='준공'?'건축 사용승인 · 운영/RFS 확인 별도':'인허가 행 기준 · 증축·대수선 포함'})),{label:'대지 식별자',value:new Set(this.base.map(x=>x.external_parcel_hint).filter(Boolean)).size,unit:'종',note:'동일 대지의 여러 허가를 묶어 대조'}].map(x=>`<article class="kpi"><div class="kpi-title">${x.label}<small>지역·검색 범위</small></div><div class="kpi-value">${num(x.value)}<em>${x.unit}</em></div><div class="kpi-detail">${x.note}</div></article>`).join('');
   $('#permitConnections').innerHTML=['ADDRESS_MATCH','NAME_HINT','AMBIGUOUS_ADDRESS','UNLINKED'].map(s=>`<div class="connection-item"><button data-connection-action="${s}">${labels[s]}</button><b>${this.base.filter(x=>x.connection?.status===s).length}건</b></div>`).join('')+`<div class="source-quality">좌표 ${this.base.filter(x=>x.location?.verification==='ADMINISTRATIVE_REPRESENTATIVE_POINT').length}건은 행정구역 대표점입니다. 면적 집계 대조 ${this.base.filter(x=>(x.areas_sqm?.dc_use_ratio_pct||0)>100).length}건.<br>허가를 센터 수에 더하거나 발표 MW를 공급 차트에 중복 반영하지 않습니다.</div>`;
   $('#permitScope').textContent=`${this.rows.length}건 / 지역·검색 범위 ${this.base.length}건 · 건축 단계 ${this.filter.stage?stageLabel(this.filter.stage):'전체'}${this.filter.year?' · 허가 '+this.filter.year+'년':''}. 시장 용량 집계와 별개의 참고 원장입니다. 상용 여부 검토 대상도 표시합니다.`;
   this.chart();this.table();this.energy();
  }
  chart(){
   const years=new Map();
   this.base.filter(x=>!this.filter.connection||x.connection?.status===this.filter.connection).forEach(x=>{for(const [i,key] of ['permit_on','construction_started_on','building_approved_on'].entries()){const v=x.dates?.[key];if(!v)continue;const year=v.slice(0,4);if(!years.has(year))years.set(year,[0,0,0]);years.get(year)[i]++;}});
   const values=[...years].sort((a,b)=>a[0].localeCompare(b[0])),max=Math.max(4,Math.ceil(Math.max(1,...values.flatMap(x=>x[1]))/4)*4),w=620,h=290,left=36,top=27,bottom=35,ph=h-top-bottom,pw=w-left-14;
   if(!values.length){$('#permitChart').innerHTML='<div class="chart-empty">현재 조건의 건축 사건이 없습니다.</div>';return;}
   let svg=`<svg viewBox="0 0 ${w} ${h}" aria-label="연도별 건축 사건 건수"><text x="${left}" y="13">건 · 허가 / 착공 / 사용승인</text>`;
   for(let i=0;i<=4;i++){const y=top+ph*(1-i/4);svg+=`<line x1="${left}" x2="${w-14}" y1="${y}" y2="${y}" stroke="#e4eaf2"/><text x="${left-7}" y="${y+4}" text-anchor="end">${max*i/4}</text>`;}
   values.forEach(([year,nums],i)=>{const step=pw/values.length,bw=Math.min(19,step*.2),x=left+step*(i+.5)-bw*1.5;svg+=`<g data-permit-year="${year}" tabindex="0" role="button" aria-label="${year}년 허가 필터"><title>${year} 허가 ${nums[0]} · 착공 ${nums[1]} · 사용승인 ${nums[2]}</title><rect x="${x-5}" y="${top}" width="${bw*3+10}" height="${ph+bottom}" fill="transparent"/>`;nums.forEach((n,j)=>{const bh=n/max*ph;svg+=`<rect x="${x+j*bw}" y="${top+ph-bh}" width="${bw-2}" height="${bh}" fill="${['#a9b7df','#5272cd','#233e82'][j]}"/>`;});svg+=`<text x="${left+step*(i+.5)}" y="${h-10}" text-anchor="middle">${year}</text></g>`;});
   $('#permitChart').innerHTML=svg+'</svg>';
   $('#permitChart').querySelectorAll('[data-permit-year]').forEach(g=>g.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();g.dispatchEvent(new MouseEvent('click',{bubbles:true}));}}));
  }
  table(){
   const pages=Math.max(1,Math.ceil(this.rows.length/10));this.filter.page=Math.min(Math.max(0,this.filter.page),pages-1);const start=this.filter.page*10;
   $('#permitRows').innerHTML=this.rows.slice(start,start+10).map(x=>`<tr><td><button class="permit-name" data-permit-id="${esc(x.candidate_id)}">${esc(x.building_name||'건물명 미표기')}</button><small>${esc(x.permit_kind||'공사 구분 미확인')} · 연면적 ${num(x.areas_sqm?.gross)}㎡</small></td><td>${esc(x.region||'')} ${esc(x.district||'')}<small class="address" title="${esc(x.address||'')}">${esc(x.address||'주소 미확인')}</small></td><td class="numeric">${x.capacities?.length?x.capacities.map(c=>`<b>${num(c.mw)} MW</b><small>${esc(capTypes[c.type]||c.type)} · 참고값</small>`).join(''):'—<small>용량 확인 필요</small>'}</td><td class="numeric">${date(x.dates?.permit_on)}<small>착공 ${date(x.dates?.construction_started_on)}</small><small>사용승인 ${date(x.dates?.building_approved_on)}</small></td><td><span class="chip ${x.permit_stage==='공사 중'?'dev':x.permit_stage==='준공'?'op':'neutral'}">${esc(stageLabel(x.permit_stage))}</span></td><td><span class="chip ${x.connection?.status==='ADDRESS_MATCH'?'op':'neutral'}">${labels[x.connection?.status]||'미확인'}</span><small>${(x.connection?.candidates||[]).map(s=>esc(s.site_name)).join(' / ')||'센터·사업자 대조 필요'}</small></td><td><button class="subtle" data-permit-id="${esc(x.candidate_id)}">근거 →</button></td></tr>`).join('')||'<tr><td colspan="7">조건에 맞는 인허가가 없습니다.</td></tr>';
   $('#permitPageInfo').textContent=this.rows.length?`${start+1}–${Math.min(start+10,this.rows.length)} / ${this.rows.length}건`:'조회 결과 없음';$('#permitPrev').disabled=this.filter.page===0;$('#permitNext').disabled=this.filter.page===pages-1;
  }
  detail(id){
   const x=this.dataset.items.find(x=>x.candidate_id===id);if(!x)return;this.selected=x;
   $('#permitTitle').textContent=x.building_name||'인허가 사업장';$('#permitDetailMeta').textContent=`${stageLabel(x.permit_stage)} · ${x.permit_kind||'공사 구분 미확인'} · ${labels[x.connection?.status]||'미확인'}`;
   const data=[['주소',x.address],['허가일',x.dates?.permit_on],['착공일',x.dates?.construction_started_on],['예정 착공일',x.dates?.construction_scheduled_on],['사용승인일',x.dates?.building_approved_on],['서비스 RFS','별도 확인 필요'],['대지 식별자',x.external_parcel_hint],['외부 허가 ID',x.external_permit_id]];
   let body='<div class="note">참고 출처에서 수집한 후보 정보입니다. 공개 원장 기준의 주소 연결이며, 개별 용량·운영 상태 확인은 별도입니다.</div><dl class="detail-facts">'+data.map(([k,v])=>`<dt>${k}</dt><dd>${esc(v||'—')}</dd>`).join('')+'</dl><button class="subtle" data-permit-map>Google 주소 조회 ↗</button>';
   body+='<h3>센터 원장 대조</h3>'+(x.connection?.candidates?.length?x.connection.candidates.map(s=>`<div class="fact-card"><button class="subtle" data-master-site="${esc(s.site_code)}">${esc(s.site_name)} →</button><p>${esc(x.connection.method)} · 사업자·건물·Phase 범위 확인</p></div>`).join(''):'<p class="unit">현재 원장과 연결되지 않았습니다. 주소·사업자 근거를 확인해 센터 후보를 대조합니다.</p>');
   body+='<h3>발표 용량과 출처</h3>'+(x.capacities?.length?x.capacities.map(c=>`<div class="basis-card"><b>${num(c.mw)} MW · ${esc(capTypes[c.type]||c.type)}</b><p>캠퍼스·건물·Phase 범위 미확인 · 공급 집계에 자동 합산하지 않습니다.</p>${(c.evidence||[]).map(e=>this.link(e.url,e.title||'용량 근거')).join('<br>')}</div>`).join(''):'<p class="unit">공개 용량 미확인</p>');
   body+='<h3>면적·좌표 확인</h3><div class="fact-card"><p>총 연면적 '+num(x.areas_sqm?.gross)+'㎡ · DC 용도 '+num(x.areas_sqm?.dc_use)+'㎡ · 비중 '+num(x.areas_sqm?.dc_use_ratio_pct)+'%</p><p>원출처 좌표 정밀도 '+esc(x.location?.source_precision||'미확인')+' · '+(x.location?.verification==='ADMINISTRATIVE_REPRESENTATIVE_POINT'?'행정구역 대표점':'독립 검증 필요')+'</p></div>';
   body+='<h3>관할 변전소 공급 여유</h3>'+Object.entries(x.infrastructure_context?.substation_headroom_mw||{}).map(([name,mw])=>`<div class="fact-card"><b>${esc(name)} · ${num(mw)} MW</b><p>센터 확보 전력과 별도입니다.</p></div>`).join('');
   body+='<h3>관련 기사</h3>'+(x.news||[]).slice(0,6).map(n=>`<div class="fact-card">${this.link(n.url,n.title||'기사')}<p>${esc(n.publisher||'')} · ${date(n.published_on)}</p></div>`).join('');
   body+='<h3>확인할 항목</h3><div class="note">'+(x.quality_warnings||[]).map(w=>esc(w)).join('<br>')+'</div>';
   body+=`<h3>담당자 검토메모</h3><form id="permitNoteForm"><label for="permitNote">내 브라우저에 보관할 메모</label><textarea id="permitNote" maxlength="4000" rows="3">${esc(this.notes[x.candidate_id]||'')}</textarea><button class="subtle" type="submit">검토메모 저장</button><span id="permitNoteStatus" role="status"></span></form>`;
   $('#permitBody').innerHTML=body;$('#permitSource').href=urls(this.dataset.source_url);$('#permitDialog').showModal();$('#permitBody').scrollTop=0;
  }
  link(url,title){const u=urls(url);return u?`<a href="${esc(u)}" target="_blank" rel="noopener">${esc(title)} ↗</a>`:'<span class="unit">근거 URL 확인 필요</span>';}
  energy(){
   const d=this.dataset?.infrastructure;if(!d)return;const selected=region(this.global?.region),rk=['광주','전남'].includes(selected)?'전남광주':selected;
   const all=(d.regions||[]).filter(x=>!selected||x.name===rk).sort((a,b)=>(b.headroom_mw??-1)-(a.headroom_mw??-1));
   const shown=this.energyAll||selected?all:all.slice(0,8),period=(all.find(x=>x.ict_period_to)||{});
   $('#energySummary').innerHTML=`<div><small>전국 변전소 그룹 여유</small><b>${num(d.national_headroom_mw)}<em>MW</em></b><span>${num(d.national_available_groups)}/${num(d.national_station_groups)}개 그룹에 여유</span></div><div><small>여유 자료 확인일</small><b class="energy-date">${esc(date(d.headroom_checked_on))}</b><span>지역 관할 합계의 중복을 제거한 전국 값</span></div>`;
   $('#energyRows').innerHTML=shown.map(x=>`<tr><td>${esc(x.name)}</td><td>${num(x.ict_average_mw)}</td><td>${num(x.self_sufficiency_pct)}</td><td>${num(x.headroom_mw)}<small>여유 ${x.available_groups}/${x.station_groups}그룹</small></td></tr>`).join('')||'<tr><td colspan="4">이 지역의 원출처 지표가 없습니다.</td></tr>';
   $('#energyNote').innerHTML=`${selected?'':'<button id="energyToggle" class="subtle">'+(this.energyAll?'상위 8개 지역':all.length+'개 지역 전체')+'</button>'}<p>정보통신업 ${esc(period.ict_period_from||'미확인')}–${esc(period.ict_period_to||'미확인')} 평균 MW · 자립도 ${esc(period.self_sufficiency_year||'미확인')}년. 전남·광주는 원출처의 합산 권역입니다.</p><p>DC IT Load·센터 확보 전력과 구분하며 지역 여유 합계끼리는 더하지 않습니다. <a href="${esc(urls(this.dataset.source_url))}" target="_blank" rel="noopener">참고 출처 ↗</a></p>`;
  }
  export(){
   const fields=['외부 허가 ID','대지 힌트','건물명','주소','공사 구분','건축 단계','허가일','착공일','사용승인일','원장 연결 상태','연결 센터','원출처 확인 상태','좌표 정밀도'];
   const rows=this.rows.map(x=>[x.external_permit_id,x.external_parcel_hint,x.building_name,x.address,x.permit_kind,x.permit_stage,x.dates?.permit_on,x.dates?.construction_started_on,x.dates?.building_approved_on,labels[x.connection?.status],(x.connection?.candidates||[]).map(s=>s.site_name).join(' / '),'참고값 · 개별 원문 검증 필요',x.location?.source_precision]);
   const blob=new Blob(['\ufeff'+[fields,...rows].map(row=>row.map(csvCell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='dc-now-permits.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
 }
 root.DCDevelopment=DCDevelopment;
})(window);
