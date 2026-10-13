(function (root) {
  'use strict';
  const known = x => x !== null && x !== undefined && x !== '' && Number.isFinite(Number(x));
  const operating = x => ['OPERATING', 'MIXED'].includes(x.lifecycle_group);
  const developing = x => ['DEVELOPMENT', 'MIXED'].includes(x.lifecycle_group);
  const commercial = x => x.commercial_scope_status === 'IN_SCOPE' && x.commercial_review_status === 'CONFIRMED';
  const published = x => x.public_visible === true && x.review_status === 'CONFIRMED';
  function scopeMatch(x, scope) {
    if (scope === 'ALL') return true;
    if (scope === 'COMMERCIAL') return commercial(x);
    if (scope === 'REVIEW') return !commercial(x) && !['CLOUD_SELF_USE', 'ENTERPRISE'].includes(x.facility_scope);
    return x.facility_scope === scope;
  }
  function missing(x) {
    const out = [];
    if (x.latitude == null || x.longitude == null) out.push(['coordinate', '좌표 확인 필요']);
    if (!['ROOFTOP', 'ROAD', 'PARCEL'].includes(x.location_precision)) out.push(['address', '상세 주소 확인 필요']);
    if (!x.lifecycle_group || x.lifecycle_group === 'UNKNOWN') out.push(['stage', '운영 단계 확인 필요']);
    if (!x.operator_names) out.push(['operator', '운영사 확인 필요']);
    if (!['operating_it_load_mw', 'development_it_load_mw', 'operating_grid_intake_mw', 'development_grid_intake_mw', 'development_announced_capacity_mw'].some(k => known(x[k]))) out.push(['capacity', '용량 확인 필요']);
    if ((developing(x)||x.lifecycle_group==='UNKNOWN')&&!x.earliest_rfs_date && !x.earliest_rfs_period) out.push(['rfs', '개발 RFS 확인 필요']);
    if (!commercial(x) && !['CLOUD_SELF_USE', 'ENTERPRISE'].includes(x.facility_scope)) out.push(['scope', '시설 범주 검토']);
    return out;
  }
  function sumKnown(rows, key) {
    const values = rows.filter(x => known(x[key]));
    return {value: values.length ? values.reduce((n, x) => n + Number(x[key]), 0) : null, known: values.length, total: rows.length,
      estimated:values.filter(x=>x.value_basis?.[key]).length,
      low:values.length?values.reduce((n,x)=>n+Number(x.value_basis?.[key]?.low_value??x[key]),0):null,
      high:values.length?values.reduce((n,x)=>n+Number(x.value_basis?.[key]?.high_value??x[key]),0):null};
  }
  function filterSites(rows, f) {
    const q = String(f.q || '').trim().toLowerCase();
    return rows.filter(x => scopeMatch(x, f.scope || 'ALL') && (!f.stage || x.lifecycle_group === f.stage) && (!f.region || x.sido === f.region) && (!f.gap || missing(x).some(y => y[0] === f.gap)) && (!q || [x.site_name, x.site_code, x.address_standard, x.operator_names, x.tracked_company_names].join(' ').toLowerCase().includes(q)));
  }
  function aggregates(rows) {
    const eligible = rows.filter(x => commercial(x) && published(x));
    const op = eligible.filter(operating), dev = eligible.filter(developing);
    return {eligible, op, dev, operating: sumKnown(op, 'operating_it_load_mw'), development: sumKnown(dev, 'development_it_load_mw')};
  }
  const basisLabels={CONFIRMED:'검증값',ANNOUNCED:'발표값',ESTIMATED:'추정',MANUAL:'담당자 입력',MANUAL_CONFIRMED:'담당자 확정',DRAFT:'수정안'};
  function planningKey(x){return [x.site_code,x.scope_type,x.scope_code,x.field_name,x.bucket].join('|');}
  function prepare(raw,include=true,drafts=[]) {
    const out=JSON.parse(JSON.stringify(raw));out.include_estimates=include;
    const values=new Map((out.planning_values||[]).map(v=>[planningKey(v),v]));
    drafts.forEach(v=>values.set(planningKey(v),v));out.planning_values=[...values.values()];
    if(!include)return out;
    const sites=new Map(out.sites.map(s=>[s.site_code,s]));
    const accepted=[];
    for(const v of values.values()){
      if(v.active===false)continue;
      const s=sites.get(v.site_code);if(!s)continue;
      const detail=(out.details||{})[v.site_code]||{},manual=['MANUAL','MANUAL_CONFIRMED'].includes(v.basis);
      const units=v.scope_type==='PROJECT'?detail.projects||[]:detail.phases||[];
      const u=v.scope_type==='SITE'?s:units.find(p=>(p.project_code===v.scope_code&&v.scope_type==='PROJECT')||(p.phase_code===v.scope_code&&v.scope_type==='PHASE'));
      if(!u)continue;
      const meta={...v,basis:v.draft?'DRAFT':v.basis};
      if(['IT_LOAD_MW','GRID_INTAKE_MW'].includes(v.field_name)){
        const bucket=v.bucket==='OPERATING'?'operating':'development',metric=v.field_name==='IT_LOAD_MW'?'it_load_mw':'grid_intake_mw',key=bucket+'_'+metric;
        const old=v.scope_type==='SITE'?s[key]:latestCapacity(detail.capacities||[],v.field_name,v.scope_type==='PHASE'?v.scope_code:null,v.scope_type==='PROJECT'?v.scope_code:u.project_code,String(out.generated_at||'').slice(0,10),v.bucket);
        if(known(old)&&!manual)continue;
        const cap={scope_type:v.scope_type,scope_label:v.scope_type==='SITE'?'센터 전체':u.phase_name||u.project_name,project_code:v.scope_type==='PROJECT'?v.scope_code:u.project_code,phase_code:v.scope_type==='PHASE'?v.scope_code:null,capacity_type_code:v.field_name,normalized_value_mw:v.value,capacity_stage:v.bucket==='OPERATING'?'OPERATING':'ANNOUNCED',measurement_basis:v.basis,published_at:v.updated_at||out.generated_at,document_url:v.source_url,planning_basis:meta.basis,method:v.method,low_value:v.low_value,high_value:v.high_value};
        detail.capacities=(detail.capacities||[]).concat(cap);accepted.push(v);
        if(v.scope_type==='SITE'){s[key]=Number(v.value);s.value_basis={...(s.value_basis||{}),[key]:meta};}
      }else{
        const key={RFS_PERIOD:v.scope_type==='SITE'?'earliest_rfs_period':'planned_rfs_period',COMPLETION_PERIOD:'planned_completion_period',STATUS_CODE:v.scope_type==='SITE'?'lifecycle_group':'status_code',ADDRESS:'address_standard',OPERATOR_NAME:'operator_names',PUE:'design_pue'}[v.field_name];
        if(u[key]!=null&&u[key]!==''&&!manual&&v.basis!=='ANNOUNCED')continue;
        if(v.field_name==='RFS_PERIOD'&&u.rfs_date&&!manual)continue;
        u[key]=v.value;u.value_basis={...(u.value_basis||{}),[key]:meta};accepted.push(v);
        if(v.field_name==='ADDRESS'&&v.scope_type==='SITE'){s.latitude=null;s.longitude=null;s.coordinate_quality='U';s.location_precision='UNKNOWN';}
      }
      if(out.details&&out.details[v.site_code])out.details[v.site_code]=detail;
    }
    for(const s of out.sites){
      const d=(out.details||{})[s.site_code];if(!d)continue;
      const changedStage=accepted.some(v=>v.site_code===s.site_code&&v.field_name==='STATUS_CODE'&&v.scope_type!=='SITE');
      if(changedStage&&!s.value_basis?.lifecycle_group){
        const states=[...(d.projects||[]),...(d.phases||[])].map(u=>u.status_code),op=states.includes('OPERATING'),dev=states.some(v=>['IDEA','SITE_SECURED','PERMITTING','POWER_SECURED','CONSTRUCTION','READY'].includes(v));
        s.lifecycle_group=op&&dev?'MIXED':op?'OPERATING':dev?'DEVELOPMENT':states.includes('ON_HOLD')?'ON_HOLD':'UNKNOWN';
        s.value_basis={...(s.value_basis||{}),lifecycle_group:{basis:'MANUAL',method:'프로젝트·Phase의 담당자 입력 상태'}};
      }
      for(const [bucket,prefix] of [['OPERATING','operating'],['DEVELOPMENT','development']])for(const [type,metric] of [['IT_LOAD_MW','it_load_mw'],['GRID_INTAKE_MW','grid_intake_mw']]){
        const key=prefix+'_'+metric;
        if(s.value_basis?.[key])continue;
        const changed=accepted.filter(v=>v.site_code===s.site_code&&v.bucket===bucket&&v.field_name===type&&v.scope_type!=='SITE');
        if(!changed.length||known(s[key])&&!changed.some(v=>['MANUAL','MANUAL_CONFIRMED'].includes(v.basis)))continue;
        const siteTotal=(raw.details?.[s.site_code]?.capacities||[]).some(c=>c.scope_type==='SITE'&&c.capacity_type_code===type&&(c.capacity_stage==='OPERATING')===(bucket==='OPERATING')&&!c.aggregation_excluded&&known(c.normalized_value_mw));
        if(siteTotal)continue;
        const nums=(d.projects||[]).filter(p=>(p.status_code==='OPERATING')===(bucket==='OPERATING')).map(p=>{
          const total=latestCapacity(d.capacities||[],type,null,p.project_code,out.generated_at.slice(0,10),bucket);if(known(total))return total;
          const children=(d.phases||[]).filter(ph=>ph.project_code===p.project_code).map(ph=>latestCapacity(d.capacities||[],type,ph.phase_code,p.project_code,out.generated_at.slice(0,10),bucket)).filter(known);
          return children.length?children.reduce((a,b)=>a+b,0):null;
        }).filter(known);
        if(nums.length){s[key]=nums.reduce((a,b)=>a+b,0);s.value_basis={...(s.value_basis||{}),[key]:{basis:'ESTIMATED',method:'프로젝트·Phase 작업값 합계',low_value:null,high_value:null}};}
      }
      const schedules=[...(d.projects||[]),...(d.phases||[])].filter(p=>p.value_basis?.planned_rfs_period&&p.status_code!=='OPERATING').sort((a,b)=>String(periodEnd(a.planned_rfs_period)).localeCompare(String(periodEnd(b.planned_rfs_period))));
      if(schedules.length&&!s.value_basis?.earliest_rfs_period){s.earliest_rfs_period=schedules[0].planned_rfs_period;s.value_basis={...(s.value_basis||{}),earliest_rfs_period:schedules[0].value_basis.planned_rfs_period};}
      out.details[s.site_code]={...d,...s,projects:d.projects,phases:d.phases,capacities:d.capacities};
    }
    out.companies=(out.companies||[]).map(company=>{
      const links=out.sites.filter(s=>commercial(s)&&published(s)&&['owner_names','operator_names','developer_names','asset_manager_names','builder_names','dbo_provider_names'].some(k=>String(s[k]||'').split(',').map(n=>n.trim()).includes(company.company_name)));
      if(!links.length)return company;
      const total=sumKnown(links.filter(operating),'operating_it_load_mw');
      return {...company,operating_it_load_mw:total.value,operating_it_estimated:total.estimated};
    });
    return out;
  }
  function latestCapacity(rows, type, phaseCode, projectCode, snapshotDate,bucket) {
    const candidates = rows.filter(x => x.capacity_type_code === type && !x.aggregation_excluded && (!x.effective_to || String(x.effective_to) >= snapshotDate) && (!bucket||!x.capacity_stage||(x.capacity_stage==='OPERATING')===(bucket==='OPERATING')) && known(x.normalized_value_mw) && (phaseCode ? x.scope_type === 'PHASE' && x.phase_code === phaseCode : x.scope_type === 'PROJECT' && x.project_code === projectCode));
    candidates.sort((a, b) => Number(['MANUAL','MANUAL_CONFIRMED','DRAFT'].includes(b.planning_basis))-Number(['MANUAL','MANUAL_CONFIRMED','DRAFT'].includes(a.planning_basis))||String(b.published_at || '').localeCompare(String(a.published_at || '')));
    return candidates.length ? Number(candidates[0].normalized_value_mw) : null;
  }
  function periodEnd(period) {
    const value=String(period||'');
    let match=value.match(/^(\d{4})[\s-]*[Qq]([1-4])$/);
    if(match)return Number(match[1])>=1900&&Number(match[1])<=2200?new Date(Date.UTC(Number(match[1]),Number(match[2])*3,0)).toISOString().slice(0,10):null;
    match=value.match(/^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/);
    if(!match)return null;
    if(Number(match[1])<1900||Number(match[1])>2200||match[2]&&(Number(match[2])<1||Number(match[2])>12))return null;
    if(match[3]){const d=new Date(value+'T00:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===value?value:null;}
    return new Date(Date.UTC(Number(match[1]),match[2]?Number(match[2]):12,0)).toISOString().slice(0,10);
  }
  function schedule(data, sites) {
    const out = [];
    const snapshotDate = String(data.generated_at || new Date().toISOString()).slice(0, 10);
    sites.filter(x => commercial(x) && published(x)).forEach(s => {
      const detail = (data.details || {})[s.site_code] || {};
      (detail.projects || []).forEach(p => {
        const phases = (detail.phases || []).filter(ph => ph.project_code === p.project_code);
        const units = phases.length ? phases : [p];
        units.forEach(u => {
          const actual = Boolean(u.rfs_date);
          const period = actual ? String(u.rfs_date) : String(u.planned_rfs_period || u.planned_rfs_date || '');
          const year = /^\d{4}/.test(period) ? Number(period.slice(0, 4)) : null;
          const bucket=u.status_code==='OPERATING'?'OPERATING':'DEVELOPMENT';
          let it = latestCapacity(detail.capacities || [], 'IT_LOAD_MW', u.phase_code, p.project_code, snapshotDate,bucket);
          let grid = latestCapacity(detail.capacities || [], 'GRID_INTAKE_MW', u.phase_code, p.project_code, snapshotDate,bucket);
          let siteBasis=null;
          if(!phases.length&&(detail.projects||[]).filter(p=>(p.status_code==='OPERATING')===(bucket==='OPERATING')).length===1){
            const prefix=bucket==='OPERATING'?'operating':'development';
            if(!known(it)&&s.value_basis?.[prefix+'_it_load_mw']){it=s[prefix+'_it_load_mw'];siteBasis=s.value_basis[prefix+'_it_load_mw'];}
            if(!known(grid)&&s.value_basis?.[prefix+'_grid_intake_mw']){grid=s[prefix+'_grid_intake_mw'];siteBasis=s.value_basis[prefix+'_grid_intake_mw'];}
          }
          const announced = latestCapacity(detail.capacities || [], 'ANNOUNCED_UNCLASSIFIED_MW', u.phase_code, p.project_code, snapshotDate);
          const estimated=Boolean(siteBasis||u.value_basis|| (detail.capacities||[]).some(c=>c.planning_basis&&(u.phase_code?c.phase_code===u.phase_code:c.project_code===p.project_code)));
          const inactive=['ON_HOLD','CANCELLED'].includes(s.lifecycle_group)||['ON_HOLD','CANCELLED'].includes(p.status_code)||['ON_HOLD','CANCELLED'].includes(u.status_code);
          out.push({site_code: s.site_code, site_name: s.site_name, region: s.sido, project_code: p.project_code, project_name: p.project_name, phase_name: u.phase_name || '프로젝트 기준 · Phase 미등록', status_code: u.status_code, completion_period: u.planned_completion_period || null, period, year, actual, estimated, inactive, overdue: !actual && Boolean(periodEnd(period)) && periodEnd(period) < snapshotDate, operating: u.status_code === 'OPERATING', it, grid, announced});
        });
      });
    });
    return out;
  }
  function annual(rows, metric) {
    const byYear = new Map();
    rows.filter(x => !x.actual && !x.operating && !x.overdue && !x.inactive && x.year !== null).forEach(x => {
      if (!byYear.has(x.year)) byYear.set(x.year, {year: x.year, total: 0, known: 0, count: 0,estimated:0});
      const item = byYear.get(x.year);item.count++;
      if(x.estimated)item.estimated++;
      if (known(x[metric])) {item.total += Number(x[metric]);item.known++;}
    });
    return [...byYear.values()].sort((a, b) => a.year - b.year);
  }
  function runState(x, now = Date.now()) {
    if (x.run_status !== 'SUCCESS') return {label: '실패·진행 상태 확인', css: 'bad'};
    if (/BACKFILL/.test(x.job_name)) return {label: '과거자료 수집 완료', css: 'op'};
    const at = Date.parse(x.finished_at || x.started_at || '');
    const hours = /RSS/.test(x.job_name) ? 12 : 36;
    if (!Number.isFinite(at) || now - at > hours * 3600000) return {label: '실행 지연', css: 'dev'};
    return {label: '최근 수집 성공', css: 'op'};
  }
  const api = {known, operating, developing, commercial, published, scopeMatch, missing, sumKnown, filterSites, aggregates, schedule, annual, runState, periodEnd,prepare,planningKey,basisLabels,latestCapacity};
  root.ManagerData = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : window);
