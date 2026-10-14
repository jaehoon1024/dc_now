(async function () {
  'use strict';
  const $ = s => document.querySelector(s);
  const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const num = x => ManagerData.known(x) ? Number(x).toLocaleString('ko-KR', {maximumFractionDigits:1}) : '—';
  const safeURL = x => { try { const u = new URL(x); return ['https:', 'http:'].includes(u.protocol) && !u.username && !u.password ? u.href : ''; } catch { return ''; } };
  const labels = {OPERATING:'운영', DEVELOPMENT:'개발', MIXED:'운영·증설', UNKNOWN:'미확인', ON_HOLD:'보류', CONSTRUCTION:'건설 중', POWER_SECURED:'전력 확보', PERMITTING:'인허가', READY:'RFS 준비', IDEA:'계획', SITE_SECURED:'부지 확보', CANCELLED:'취소'};
  const fieldNames = {IT_LOAD_MW:'IT Load', GRID_INTAKE_MW:'수전용량', RFS_PERIOD:'RFS', COMPLETION_PERIOD:'준공', STATUS_CODE:'단계', ADDRESS:'주소', OPERATOR_NAME:'운영사', PUE:'PUE'};
  const compactRegion = x => String(x === '__UNKNOWN__' ? '지역 미확인' : x || '미확인').replace('특별자치도','').replace('특별자치시','').replace('특별시','').replace('광역시','').replace('경기도','경기').replace('충청남도','충남').replace('충청북도','충북').replace('경상남도','경남').replace('경상북도','경북').replace('전라남도','전남').replace('전라북도','전북');
  const isOp = s => ['OPERATING','MIXED'].includes(s.lifecycle_group);
  const isDev = s => ['DEVELOPMENT','MIXED'].includes(s.lifecycle_group);
  const chip = s => `<span class="chip ${s === 'OPERATING' ? 'op' : s === 'MIXED' ? 'mixed' : ['DEVELOPMENT','CONSTRUCTION','PERMITTING','POWER_SECURED','READY','IDEA','SITE_SECURED'].includes(s) ? 'dev' : 'neutral'}">${esc(labels[s] || s || '미확인')}</span>`;
  const date = x => x ? String(x).slice(0,10) : '일자 미표기';
  const time = x => x ? new Date(x).toLocaleString('ko-KR', {month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Seoul'}) : '시각 미확인';
  const state = {scope:'COMMERCIAL', region:'', q:'', include:true, stage:'', year:null, metric:'it', sort:'default', desc:true, page:0};
  let raw, data, rows = [], base = [], schedule = [], selected = null, mapController=null, development=null;
  const legacy=/^#(detail|register|projects|companies|review|sources|ops|map)(?:\/|$)/;
  if(legacy.test(location.hash)){location.replace('./manage.html'+location.hash);return;}
  window.addEventListener('hashchange',()=>{if(legacy.test(location.hash))location.replace('./manage.html'+location.hash);});
  const draftStore='dc-now-planning-drafts-v1';
  let drafts = [];
  function readDrafts(){try {const values=JSON.parse(localStorage.getItem(draftStore)||'[]');drafts=Array.isArray(values)?values.filter(x=>x&&typeof x==='object'&&!Array.isArray(x)):[];}catch{drafts=[];}}
  try { const v = JSON.parse(localStorage.getItem('dc-now-planning-drafts-v1') || '[]'); if (Array.isArray(v)) drafts = v.filter(x=>x&&typeof x==='object'&&!Array.isArray(x)); } catch { /* A disabled store should not prevent viewing the snapshot. */ }
  try {
    const embedded = $('#conceptSnapshot');
    if (embedded) raw = JSON.parse(embedded.textContent);
    else { const response = await fetch('./data.json', {cache:'no-store'}); if (!response.ok) throw new Error('공개 스냅샷을 불러오지 못했습니다.'); raw = await response.json(); }
    if (!Array.isArray(raw.sites) || !raw.details) throw new Error('공개 스냅샷 형식이 올바르지 않습니다.');
    $('#snapshotAt').textContent = new Date(raw.generated_at).toLocaleString('ko-KR', {timeZone:'Asia/Seoul',hour12:false});
    [...new Set(raw.sites.map(s => s.sido).filter(Boolean))].sort().forEach(r => $('#region').add(new Option(compactRegion(r),r)));
    if(raw.sites.some(s=>!s.sido))$('#region').add(new Option('지역 미확인','__UNKNOWN__'));
    development=new DCDevelopment({onCenter:openDetail,onAddress:(address,name)=>{selected=null;$('#googleCanvas').hidden=true;$('#googleMap').hidden=false;$('#googleMap').src='https://maps.google.com/maps?q='+encodeURIComponent(address||name||'대한민국')+'&z=15&output=embed';$('#mapCaption').textContent=(name||'인허가 사업장')+' · 주소 검색 · 좌표 검증 별도';$('#location').scrollIntoView({behavior:'smooth',block:'center'});}});
    wire(); render(); $('#initialMarket')?.setAttribute('hidden','');
    mapController = new DCGoogleMap($('#googleCanvas'), {onSelect:openDetail,onStatus:message=>{$('#mapStatus').textContent=message;$('#bubbleMetric').disabled=$('#approximateCoordinates').disabled=!mapController?.ready;$('#mapLegend').hidden=!mapController?.ready;},onReady:()=>{$('#googleMap').hidden=true;$('#googleCanvas').hidden=false;renderMapRegions();}});
    await mapController.init('./map-config.json'); renderMapRegions();
  } catch (e) { $('#error').hidden = false; $('#error').textContent = e.message; }
  function basis(s, key) { return s.value_basis?.[key] ? ManagerData.basisLabels[s.value_basis[key].basis] || '작업값' : ManagerData.known(s[key]) ? '검증값' : '미확인'; }
  function wire() {
    $('#scope').addEventListener('change', e => {state.scope=e.target.value; resetDependent(); render();});
    $('#region').addEventListener('change', e => {state.region=e.target.value; resetDependent(); render();});
    $('#search').addEventListener('input', e => {state.q=e.target.value; state.page=0; state.year=null; render();});
    document.querySelectorAll('[name=basis]').forEach(e => e.addEventListener('change', () => {state.include=e.value==='planning'; state.page=0; render();}));
    document.querySelectorAll('[data-stage]').forEach(e => e.addEventListener('click', () => {state.stage=e.dataset.stage; state.page=0; state.year=null; render();}));
    document.querySelectorAll('[data-metric]').forEach(e => e.addEventListener('click', () => {state.metric=e.dataset.metric; renderChart();}));
    document.querySelectorAll('[data-sort]').forEach(e => e.addEventListener('click', () => {state.desc=state.sort===e.dataset.sort?!state.desc:true; state.sort=e.dataset.sort; state.page=0; renderTable();}));
    $('#reset').addEventListener('click', () => {
      Object.assign(state,{scope:'COMMERCIAL',region:'',q:'',include:true,stage:'',year:null,metric:'it',page:0,sort:'default',desc:true});
      $('#scope').value=state.scope;$('#region').value='';$('#search').value='';$('[name=basis][value=planning]').checked=true;
      $('#bubbleMetric').value='it';$('#approximateCoordinates').checked=false;
      development?.reset();nationalMap();render();
    });
    $('#prev').addEventListener('click', () => {state.page--; renderTable();});
    $('#next').addEventListener('click', () => {state.page++; renderTable();});
    $('#nationalMap').addEventListener('click', nationalMap);
    $('#bubbleMetric').addEventListener('change',renderMapRegions);
    $('#approximateCoordinates').addEventListener('change',renderMapRegions);
    window.addEventListener('storage',e=>{if(e.key===draftStore||e.key===null){readDrafts();render();}});
    $('#closeDetail').addEventListener('click', () => $('#detailDialog').close());
    $('#detailDialog').addEventListener('click', e => {if(e.target===$('#detailDialog') && e.offsetX<0)$('#detailDialog').close();});
    $('#download').addEventListener('click', download);
    $('main').addEventListener('click', e => {
      const detail=e.target.closest('[data-detail]'); if(detail){openDetail(detail.dataset.detail); return;}
      const map=e.target.closest('[data-map]'); if(map){selectMap(map.dataset.map);$('#location').scrollIntoView({behavior:'smooth',block:'center'});return;}
      const region=e.target.closest('[data-region]');if(region){state.region=region.dataset.region;$('#region').value=state.region;resetDependent();render();return;}
      const company=e.target.closest('[data-company]');if(company){state.q=company.dataset.company;$('#search').value=state.q;resetDependent();render();return;}
      const year=e.target.closest('[data-year]');if(year){state.year=state.year===Number(year.dataset.year)?null:Number(year.dataset.year);state.page=0;render();}
    });
  }
  function resetDependent(){state.page=0;state.year=null;}
  function render() {
    data=ManagerData.prepare(raw,state.include,drafts);
    base=ManagerData.filterSites(data.sites,{scope:state.scope,region:state.region==='__UNKNOWN__'?'':state.region,q:state.q});
    if(state.region==='__UNKNOWN__')base=base.filter(s=>!s.sido);
    rows=ManagerData.filterSites(base,{stage:state.stage});
    if(state.year){const codes=new Set(ManagerData.schedule(data,rows).filter(s=>s.year===state.year&&!s.actual&&!s.operating&&!s.overdue&&!s.inactive).map(s=>s.site_code));rows=rows.filter(s=>codes.has(s.site_code));}
    schedule=ManagerData.schedule(data,rows);
    $('#scopeNote').textContent=[$('#scope option:checked').textContent,state.region?compactRegion(state.region):'전국',state.stage?labels[state.stage]:'전체 단계',state.year?`RFS ${state.year}년`:'',`${rows.length}곳`].filter(Boolean).join(' · ');
    document.querySelectorAll('[data-stage]').forEach(b=>{b.setAttribute('aria-pressed',String(b.dataset.stage===state.stage));b.querySelector('span').textContent=b.dataset.stage?base.filter(s=>s.lifecycle_group===b.dataset.stage).length:base.length;});
    if(selected&&!rows.some(s=>s.site_code===selected))nationalMap();
    renderKpis();renderChart();renderMapRegions();renderTable();renderRankings();renderCoverage();renderEvidence();renderRuns();development?.update(data,state);
  }
  function renderKpis() {
    const op=rows.filter(isOp),dev=rows.filter(isDev),operating=ManagerData.sumKnown(op,'operating_it_load_mw'),development=ManagerData.sumKnown(dev,'development_it_load_mw');
    const strict=ManagerData.filterSites(raw.sites,{scope:state.scope,region:state.region==='__UNKNOWN__'?'':state.region,q:state.q,stage:state.stage}).filter(s=>rows.some(r=>r.site_code===s.site_code));
    const strictOp=ManagerData.sumKnown(strict.filter(isOp),'operating_it_load_mw'),strictDev=ManagerData.sumKnown(strict.filter(isDev),'development_it_load_mw');
    const items=[{title:'운영 센터',tag:'현재',value:op.length,unit:'곳',detail:`운영·증설 병행 ${rows.filter(s=>s.lifecycle_group==='MIXED').length}곳 포함`,foot:'캠퍼스 단위 · 실제 가동률과 구분'},
      {title:'개발 센터',tag:'계획·건설',value:dev.length,unit:'곳',detail:`RFS 일정 연결 ${schedule.filter(s=>!s.actual&&!s.operating&&!s.inactive).length}개 사업`,foot:'계획부터 건설까지 · 준공과 RFS 별도'},
      {title:'운영 IT Load',tag:state.include?'추정 포함':'원문 검증',value:operating.value,unit:'MW',estimated:operating.estimated,detail:`용량 확보 ${operating.known}/${op.length}곳 · 검증 ${strictOp.known}곳`,foot:operating.estimated?`작업 범위 ${num(operating.low)}–${num(operating.high)} MW`:'원문으로 확인된 값의 합계'},
      {title:'개발 IT Load',tag:state.include?'추정 포함':'원문 검증',value:development.value,unit:'MW',estimated:development.estimated,detail:`용량 확보 ${development.known}/${dev.length}곳 · 검증 ${strictDev.known}곳`,foot:development.estimated?`작업 범위 ${num(development.low)}–${num(development.high)} MW`:'센터 전체 용량 · 연도별 공급과 범위 다름'}];
    $('#kpis').innerHTML=items.map(i=>`<article class="kpi"><div class="kpi-title">${i.title}<small>${i.tag}</small></div><div class="kpi-value">${i.estimated?'<span class="estimate-mark">≈</span>':''}${num(i.value)}<em>${i.unit}</em></div><div class="kpi-detail">${i.detail}</div><div class="kpi-foot">${i.foot}</div></article>`).join('');
    $('#basisNote').innerHTML=state.include?'<span><strong>추정 포함 보기</strong> · 발표·모델 추정·담당자 입력을 포함한 작업용 시나리오입니다. 시장 실측 총량과 구분합니다.</span><span>계약·LOI가 없으면 가용용량을 계산하지 않습니다.</span>':'<span><strong>원문 검증 보기</strong> · 공개 근거로 검증한 수치만 합산합니다. 미확인 용량은 0이 아닌 —로 표시합니다.</span>';
  }
  function renderChart() {
    document.querySelectorAll('[data-metric]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.metric===state.metric)));
    const annual=ManagerData.annual(schedule,'it');
    const items=annual.map(r=>({...r,value:state.metric==='count'?r.count:r.known?r.total:null}));
    const future=schedule.filter(s=>!s.actual&&!s.operating&&!s.overdue&&!s.inactive);
    const missing=schedule.filter(s=>!s.actual&&!s.operating&&!s.overdue&&!s.inactive&&!s.year).length;
    $('#supplyNote').textContent=`상용·공개 근거가 있는 사업만 집계 · 미래 ${future.length}개 / 일정 미확인 ${missing}개. 준공일을 RFS로 대체하지 않으며 캠퍼스 용량을 Phase마다 반복하지 않습니다.${state.year?' 연도 막대를 다시 누르면 필터를 해제합니다.':''}`;
    if(!items.length){$('#supplyChart').innerHTML='<div class="chart-empty"><b>집계할 RFS 일정이 없습니다.</b><span>조건을 바꾸거나 추정 포함 보기로 확인하세요.</span></div>';return;}
    const width=620,height=310,left=43,right=13,top=32,bottom=38,plotH=height-top-bottom,plotW=width-left-right,max=Math.max(1,...items.map(r=>r.value||0))*1.22;
    let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="연도별 신규 공급 전망"><text x="${left}" y="15">${state.metric==='count'?'사업 수':state.include?'MW · 추정 포함 시나리오':'MW · 원문 검증값'}</text>`;
    for(let i=0;i<5;i++){const y=top+plotH*(1-i/4);svg+=`<line x1="${left}" y1="${y}" x2="${width-right}" y2="${y}" stroke="#e4eaf2"/><text x="${left-9}" y="${y+4}" text-anchor="end">${num(max*i/4)}</text>`;}
    items.forEach((r,i)=>{const space=plotW/items.length,barW=Math.min(56,space*.45),x=left+space*(i+.5)-barW/2,h=(r.value||0)/max*plotH,y=top+plotH-h;svg+=`<g class="chart-column" data-year="${r.year}" tabindex="0" role="button" aria-label="${r.year}년 ${num(r.value)}${state.metric==='count'?'개 사업':'MW'} 필터" aria-pressed="${state.year===r.year}"><title>${r.year}년 ${num(r.value)} · ${r.known}/${r.count}개 용량 확보</title><rect x="${x-10}" y="${top}" width="${barW+20}" height="${plotH+bottom}" fill="transparent"/>${r.value===null?`<text x="${x+barW/2}" y="${top+plotH/2}" text-anchor="middle">용량 미확인</text>`:`<rect class="capacity-bar" x="${x}" y="${y}" width="${barW}" height="${h}" rx="2" fill="${state.year===r.year?'#203f9e':r.estimated?'#98ace3':'#355bd1'}"/><text x="${x+barW/2}" y="${y-10}" text-anchor="middle" class="bar-value">${num(r.value)}</text>`}<text x="${x+barW/2}" y="${height-12}" text-anchor="middle">${r.year}</text></g>`;});
    $('#supplyChart').innerHTML=svg+'</svg>';
    $('#supplyChart').querySelectorAll('[data-year]').forEach(g=>g.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();g.dispatchEvent(new MouseEvent('click',{bubbles:true}));}}));
  }
  function regionGroups() {
    const groups=new Map();rows.forEach(s=>{const key=s.sido||'__UNKNOWN__';if(!groups.has(key))groups.set(key,[]);groups.get(key).push(s);});
    return [...groups].map(([name,sites])=>({name,sites,op:ManagerData.sumKnown(sites.filter(isOp),'operating_it_load_mw').value,dev:ManagerData.sumKnown(sites.filter(isDev),'development_it_load_mw').value}));
  }
  function renderMapRegions() {
    mapController?.update(rows, {metric:$('#bubbleMetric').value,approximate:$('#approximateCoordinates').checked});
    $('#mapRegions').innerHTML=regionGroups().sort((a,b)=>b.sites.length-a.sites.length).slice(0,6).map(r=>`<button class="map-region" data-region="${esc(r.name)}"><span>${esc(compactRegion(r.name))}</span><b>${r.sites.length}곳</b></button>`).join('')||'<small>조회 결과 없음</small>';
    const precise=rows.filter(s=>s.latitude!=null&&s.longitude!=null&&['A','B'].includes(s.coordinate_quality)).length;
    $('#mapQuality').textContent=`검증 좌표 ${precise}/${rows.length}곳. 주소 조회와 DB 좌표 검증은 구분합니다.`;
  }
  function selectMap(code){const s=data.sites.find(s=>s.site_code===code);if(!s)return;const q=s.address_standard||(s.latitude!=null&&s.longitude!=null?`${s.latitude},${s.longitude}`:'');selected=code;if(mapController?.select(s)){$('#googleMap').hidden=true;$('#googleCanvas').hidden=false;}else{$('#googleMap').hidden=false;$('#googleCanvas').hidden=true;}$('#googleMap').src=`https://maps.google.com/maps?q=${encodeURIComponent(q||s.site_name)}&z=${q?15:8}&output=embed`;$('#mapCaption').textContent=`${s.site_name} · ${q?'주소 조회 · DB 좌표와 구분':'센터명 검색 · 위치 확인 필요'}`;}
  function nationalMap(){selected=null;if(mapController?.ready){$('#googleMap').hidden=true;$('#googleCanvas').hidden=false;mapController.fit();}$('#googleMap').src='https://maps.google.com/maps?q=대한민국&z=7&output=embed';$('#mapCaption').textContent='전국 조회 · 센터 선택 시 주소로 이동';}
  function capacityCell(s,metric) {
    const opKey='operating_'+metric,devKey='development_'+metric;
    const parts=[];
    if(isOp(s))parts.push(`<div><b>${num(s[opKey])}</b><span class="basis-inline">${esc(basis(s,opKey))}</span></div>`);
    if(isDev(s))parts.push(`<div>${isOp(s)?'개발 ':''}<b>${num(s[devKey])}</b><span class="basis-inline">${esc(basis(s,devKey))}</span></div>`);
    return parts.join('')||'—';
  }
  function rfsValue(s){return s.earliest_rfs_period||s.earliest_rfs_date||'';}
  function sortedRows(){return [...rows].sort((a,b)=>{
    if(state.sort==='it'){const value=s=>{const v=[s.operating_it_load_mw,s.development_it_load_mw].filter(ManagerData.known);return v.length?v.reduce((x,y)=>x+Number(y),0):null;};const av=value(a),bv=value(b);if(av===null||bv===null)return av===bv?0:av===null?1:-1;return (av-bv)*(state.desc?-1:1);}
    if(state.sort==='rfs'){const av=rfsValue(a),bv=rfsValue(b);if(!av||!bv)return av===bv?0:av? -1:1;return av.localeCompare(bv)*(state.desc?-1:1);}
    const priority=s=>isDev(s)?0:isOp(s)?1:2;
    return priority(a)-priority(b)||rfsValue(a).localeCompare(rfsValue(b))||a.site_name.localeCompare(b.site_name,'ko');
  });}
  function renderTable() {
    const count=rows.length,pages=Math.max(1,Math.ceil(count/10));state.page=Math.max(0,Math.min(state.page,pages-1));
    $('#resultCount').textContent=`${count}곳 / 조회 범위 ${base.length}곳`;
    $('#siteRows').innerHTML=sortedRows().slice(state.page*10,state.page*10+10).map(s=>`<tr><td><button data-detail="${esc(s.site_code)}">${esc(s.site_name)}</button><small>${esc(s.operator_names||'운영사 미확인')}</small></td><td>${esc(compactRegion(s.sido))} ${esc(s.sigungu||'')}<small class="address" title="${esc(s.address_standard||'')}">${esc(s.address_standard||'상세 주소 확인 필요')}</small><button class="subtle" data-map="${esc(s.site_code)}">지도 ↗</button></td><td>${chip(s.lifecycle_group)}</td><td class="numeric">${capacityCell(s,'it_load_mw')}</td><td class="numeric">${capacityCell(s,'grid_intake_mw')}</td><td class="numeric">${esc(rfsValue(s)||'—')}<small>${rfsValue(s)?esc(s.value_basis?.earliest_rfs_period?ManagerData.basisLabels[s.value_basis.earliest_rfs_period.basis]:'검증 일정'):isDev(s)?'RFS 확인 필요':'운영 중'}</small></td><td>${s.latitude!=null&&s.longitude!=null&&['A','B'].includes(s.coordinate_quality)?'<span class="chip op">좌표 검증</span>':'<span class="chip neutral">좌표 확인 필요</span>'}<small>${date(s.latest_data_update)}</small></td><td><button class="subtle" data-detail="${esc(s.site_code)}">열기 →</button></td></tr>`).join('')||'<tr><td colspan="8">조건에 맞는 센터가 없습니다. 조회 조건을 초기화해 주세요.</td></tr>';
    $('#pageInfo').textContent=count?`${state.page*10+1}–${Math.min((state.page+1)*10,count)} / ${count}곳`:'조회 결과 없음';
    $('#prev').disabled=state.page===0;$('#next').disabled=state.page>=pages-1;
  }
  function rankHTML(groups,kind) {
    groups.sort((a,b)=>(b.op||0)+(b.dev||0)-(a.op||0)-(a.dev||0));
    const max=Math.max(1,...groups.map(r=>(r.op||0)+(r.dev||0)));
    return groups.slice(0,7).map(r=>{const unknown=r.op===null&&r.dev===null,total=unknown?null:(r.op||0)+(r.dev||0);return `<div class="rank-row"><button data-${kind}="${esc(r.name)}" title="${esc(r.name)}">${esc(kind==='region'?compactRegion(r.name):r.name)}</button><div class="rank-track"><span style="width:${(r.op||0)/max*100}%"></span><span class="dev-segment" style="width:${(r.dev||0)/max*100}%"></span></div><b>${num(total)}</b></div>`;}).join('')||'<p class="unit">조회 조건에 맞는 연결 정보가 없습니다.</p>';
  }
  function renderRankings() {
    $('#regionBars').innerHTML=rankHTML(regionGroups(),'region');
    const companies=new Map();rows.forEach(s=>{String(s.operator_names||'').split(',').map(n=>n.trim()).filter(Boolean).forEach(n=>{if(!companies.has(n))companies.set(n,[]);companies.get(n).push(s);});});
    $('#companyBars').innerHTML=rankHTML([...companies].map(([name,sites])=>({name,op:ManagerData.sumKnown(sites.filter(isOp),'operating_it_load_mw').value,dev:ManagerData.sumKnown(sites.filter(isDev),'development_it_load_mw').value})),'company');
  }
  function renderCoverage() {
    const codes=new Set(rows.map(s=>s.site_code)),strict=raw.sites.filter(s=>codes.has(s.site_code)),n=rows.length;
    const sourceCount=strict.filter(s=>{const d=raw.details[s.site_code];return d&&(d.verified_facts?.length||d.capacities?.some(c=>c.document_url)||s.commercial_source_url);}).length;
    const metrics=[['IT Load 원문 검증',strict.filter(s=>[s.operating_it_load_mw,s.development_it_load_mw].some(ManagerData.known)).length,`작업값 포함 ${rows.filter(s=>[s.operating_it_load_mw,s.development_it_load_mw].some(ManagerData.known)).length}/${n}곳 · 값 상태는 센터 상세에서 확인`],['수전용량 원문 검증',strict.filter(s=>[s.operating_grid_intake_mw,s.development_grid_intake_mw].some(ManagerData.known)).length,'발표 총용량과 IT Load는 별도 항목'],['A/B 등급 좌표 검증',strict.filter(s=>s.latitude!=null&&s.longitude!=null&&['A','B'].includes(s.coordinate_quality)).length,'행정구역 대표점과 건물·필지 위치를 구분'],['센터 상세의 공개 근거 연결',sourceCount,'공개 상세에 실제 URL 또는 검증 항목이 연결된 센터']];
    $('#coverage').innerHTML=metrics.map(([name,value,note])=>`<div class="coverage-row"><div class="coverage-label"><span>${name}</span><b>${value}/${n}곳</b></div><div class="coverage-track"><span style="width:${n?value/n*100:0}%"></span></div><small>${esc(note)}</small></div>`).join('');
  }
  function renderEvidence() {
    $('#evidenceTotal').textContent=`누적 ${num(raw.evidence_summary?.total_document_count)}건`;
    $('#evidence').innerHTML=(raw.recent_evidence||[]).slice(0,6).map(d=>{const url=safeURL(d.canonical_url);return `<div class="news-item"><time>${d.published_at?date(d.published_at).slice(2):'일자 미표기'}</time><div>${url?`<a href="${esc(url)}" target="_blank" rel="noopener">${esc(d.title)} ↗</a>`:`<span>${esc(d.title)}</span>`}<small>${esc(d.publisher||d.source_code)} · 등급 ${esc(d.source_grade||'미지정')}</small></div></div>`;}).join('')||'<p class="unit">공개 근거 없음</p>';
  }
  function renderRuns() {
    const names={RSS_DAILY:'RSS 뉴스',NEWSROOM_DAILY:'사업자 뉴스룸',OPENDART_DAILY:'OpenDART 공시'};
    const runs=(raw.collection_status||[]).filter(r=>!/BACKFILL/.test(r.job_name));
    const external=data.development_intelligence?.collection,externalAge=external?Date.now()-Date.parse(external.last_success_at||''):null,externalStale=external?.status==='SUCCESS'&&(!Number.isFinite(externalAge)||externalAge>36*3600000);
    $('#runs').innerHTML=(external?`<div class="run-row"><div><b>인허가·전력 참고자료</b><small>${esc(time(external.last_success_at))} KST · NamePF 공개 사실값</small></div><div><span class="chip ${external.status==='SUCCESS'?externalStale?'dev':'op':'bad'}">${external.status==='SUCCESS'?externalStale?'수집 지연 확인':'최근 수집 성공':'실패 · 이전 자료 유지'}</span><span class="run-count">신규 ${num(external.added_records)}건 · 변경 ${num(external.changed_records)}건</span></div></div>`:'')+runs.slice(0,4).map(r=>{const rs=ManagerData.runState(r);return `<div class="run-row"><div><b>${esc(names[r.job_name]||r.job_name)}</b><small>${esc(time(r.finished_at||r.started_at))} KST · ${r.success_source_count??0}/${r.total_source_count??0}개 소스</small></div><div><span class="chip ${rs.css==='op'?'op':rs.css==='dev'?'dev':'bad'}">${esc(rs.label)}</span><span class="run-count">신규 ${num(r.new_document_count)}건</span></div></div>`;}).join('');
    const s=raw.source_assessment?.summary||{};
    $('#sourceQuality').innerHTML=`등록 소스 ${num(s.registered_sources)}개 · 문서 기여 ${num(s.contributing_sources)}개<br>뉴스 집계 URL 비중 ${num(s.aggregator_share_pct)}% · 기사 탐색에서 사업자·기관 원문 확보로 확장할 필요가 있습니다.`;
  }
  function openDetail(code) {
    const s=data.sites.find(s=>s.site_code===code);if(!s)return;
    const d=data.details[code]||{},op=ManagerData.sumKnown(isOp(s)?[s]:[],'operating_it_load_mw'),dev=ManagerData.sumKnown(isDev(s)?[s]:[],'development_it_load_mw');
    $('#detailTitle').textContent=s.site_name;
    $('#detailMeta').innerHTML=`${chip(s.lifecycle_group)} ${esc(compactRegion(s.sido))} ${esc(s.sigungu||'')} · ${esc(s.operator_names||'운영사 미확인')}`;
    const models=(data.planning_values||[]).filter(v=>v.site_code===code&&v.active!==false);
    const detailSchedule=ManagerData.schedule(data,[s]);
    let html=`<div class="drawer-metrics"><div><small>운영 IT Load</small><b>${num(op.value)}<em>MW</em></b></div><div><small>개발 IT Load</small><b>${num(dev.value)}<em>MW</em></b></div><div><small>다음 RFS</small><b style="font-size:17px">${esc(rfsValue(s)||'—')}</b></div></div><div class="note">${state.include?'추정 포함 보기입니다. 캠퍼스 전체 용량과 개별 Phase 용량은 서로 다른 범위입니다.':'원문으로 검증한 수치만 표시합니다.'} 가용용량은 계약·LOI 정보 확보 후 계산합니다.</div>`;
    html+=`<dl class="detail-facts"><dt>주소</dt><dd>${esc(s.address_standard||'확인 필요')}</dd><dt>소유주</dt><dd>${esc(d.owner_names||'확인 필요')}</dd><dt>개발사</dt><dd>${esc(d.developer_names||'확인 필요')}</dd><dt>자산운용사</dt><dd>${esc(d.asset_manager_names||'확인 필요')}</dd><dt>시공사</dt><dd>${esc(d.builder_names||'확인 필요')}</dd><dt>마지막 갱신</dt><dd>${esc(date(s.latest_data_update))}</dd></dl>`;
    html+='<h3>프로젝트·Phase / RFS</h3>';
    html+=detailSchedule.map(u=>`<div class="phase-card"><div><b>${esc(u.phase_name)}</b>${chip(u.status_code)}</div><p>${esc(u.project_name)}</p><p>IT ${num(u.it)} MW · 수전 ${num(u.grid)} MW · ${u.actual?'실제 RFS':'RFS 예정'} ${esc(u.period||'미확인')}${u.estimated?' · 작업값 포함':''}</p>${u.completion_period?`<p>준공 예정 ${esc(u.completion_period)} · RFS와 별도</p>`:''}</div>`).join('')||'<p class="unit">현재 범위에서 연결된 사업 일정이 없습니다.</p>';
    html+='<h3>발표·추정·담당자 입력</h3>';
    html+=models.map(v=>{const url=safeURL(v.source_url),numeric=['IT_LOAD_MW','GRID_INTAKE_MW','PUE'].includes(v.field_name),unit=v.field_name.includes('_MW')?' MW':'';return `<div class="basis-card"><b>${esc(fieldNames[v.field_name]||v.field_name)} · ${numeric?num(v.value):esc(v.value)}${unit}</b><span class="chip ${v.basis==='ANNOUNCED'?'op':'dev'}">${esc(v.draft?'수정안':ManagerData.basisLabels[v.basis]||v.basis)}</span><p>${v.scope_type==='SITE'?'캠퍼스 전체':esc(v.scope_code)} · ${v.bucket==='OPERATING'?'운영':v.bucket==='DEVELOPMENT'?'개발':'기본정보'}${v.low_value!=null&&v.high_value!=null?` · 범위 ${num(v.low_value)}–${num(v.high_value)}${unit}`:''}</p><p>${esc(v.method||'산정 근거 미표기')}</p>${url?`<a href="${esc(url)}" target="_blank" rel="noopener">산정 근거 원문 ↗</a>`:''}</div>`;}).join('')||'<p class="unit">등록된 작업값이 없습니다.</p>';
    const permits=(data.development_intelligence?.items||[]).filter(r=>r.connection?.site_code===code);
    if(permits.length)html+='<h3>주소로 연결한 건축 인허가</h3>'+permits.map(r=>'<div class="fact-card"><b>'+esc(r.building_name||'건물명 미표기')+' · '+esc(r.permit_stage==='준공'?'사용승인':r.permit_stage)+'</b><p>'+esc(r.permit_kind)+' · 허가 '+esc(r.dates?.permit_on||'—')+' · 착공 '+esc(r.dates?.construction_started_on||'—')+' · 사용승인 '+esc(r.dates?.building_approved_on||'—')+'</p>'+(r.workbook_reference?'<p>용도지역 '+esc(r.workbook_reference.facts?.zoning||'—')+' · 용적률 '+num(r.workbook_reference.facts?.floor_area_ratio_pct)+'% · 대장 변경 '+esc(r.workbook_reference.facts?.registry_changed_on||'—')+'</p><small>첨부 목록 '+esc(r.workbook_reference.source_name)+' '+num(r.workbook_reference.source_row)+'행</small>':'')+'<p>원장 연결 · RFS/용량 확정 별도</p></div>').join('');
    html+='<h3>원문 검증 근거</h3>';
    html+=(d.verified_facts||[]).slice(0,6).map(f=>{const url=safeURL(f.canonical_url);return `<div class="fact-card"><b>${esc(f.field_name)} · ${esc(f.normalized_value)}</b><p>${esc(f.evidence_locator||'')} · 확인 ${date(f.reviewed_at)}</p>${url?`<a href="${esc(url)}" target="_blank" rel="noopener">출처 확인 ↗</a>`:''}</div>`;}).join('')||'<p class="unit">등록된 검증 항목이 없습니다.</p>';
    $('#detailBody').innerHTML=html;
    $('#editorLink').href=`./manage.html#detail/${encodeURIComponent(code)}/planning`;
    selectMap(code);$('#detailDialog').showModal();$('#detailBody').scrollTop=0;
  }
  function download() {
    const fields=['센터','지역','단계','운영 IT MW','운영 IT 상태','개발 IT MW','개발 IT 상태','다음 RFS','보기 기준'];
    const values=sortedRows().map(s=>[s.site_name,s.sido,labels[s.lifecycle_group]||s.lifecycle_group,s.operating_it_load_mw??'',basis(s,'operating_it_load_mw'),s.development_it_load_mw??'',basis(s,'development_it_load_mw'),rfsValue(s),state.include?'추정 포함':'원문 검증']);
    const cell=x=>'"'+String(x).replace(/^[\s]*[=+\-@]/,"'$&").replace(/"/g,'""')+'"';
    const blob=new Blob(['\ufeff'+[fields,...values].map(r=>r.map(cell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='dc-now-market.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
})();
