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
    if (!x.earliest_rfs_date && !x.earliest_rfs_period) out.push(['rfs', 'RFS 확인 필요']);
    if (!commercial(x) && !['CLOUD_SELF_USE', 'ENTERPRISE'].includes(x.facility_scope)) out.push(['scope', '시설 범주 검토']);
    return out;
  }
  function sumKnown(rows, key) {
    const values = rows.filter(x => known(x[key]));
    return {value: values.length ? values.reduce((n, x) => n + Number(x[key]), 0) : null, known: values.length, total: rows.length};
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
  function latestCapacity(rows, type, phaseCode, projectCode, snapshotDate) {
    const candidates = rows.filter(x => x.capacity_type_code === type && !x.aggregation_excluded && (!x.effective_to || String(x.effective_to) >= snapshotDate) && known(x.normalized_value_mw) && (phaseCode ? x.scope_type === 'PHASE' && x.phase_code === phaseCode : x.scope_type === 'PROJECT' && x.project_code === projectCode));
    candidates.sort((a, b) => String(b.published_at || '').localeCompare(String(a.published_at || '')));
    return candidates.length ? Number(candidates[0].normalized_value_mw) : null;
  }
  function periodEnd(period) {
    const value=String(period||'');
    let match=value.match(/^(\d{4})\s*[Qq]([1-4])$/);
    if(match)return new Date(Date.UTC(Number(match[1]),Number(match[2])*3,0)).toISOString().slice(0,10);
    match=value.match(/^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/);
    if(!match)return null;
    if(match[3])return value;
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
          const it = latestCapacity(detail.capacities || [], 'IT_LOAD_MW', u.phase_code, p.project_code, snapshotDate);
          const grid = latestCapacity(detail.capacities || [], 'GRID_INTAKE_MW', u.phase_code, p.project_code, snapshotDate);
          const announced = latestCapacity(detail.capacities || [], 'ANNOUNCED_UNCLASSIFIED_MW', u.phase_code, p.project_code, snapshotDate);
          out.push({site_code: s.site_code, site_name: s.site_name, region: s.sido, project_code: p.project_code, project_name: p.project_name, phase_name: u.phase_name || '프로젝트 기준 · Phase 미등록', status_code: u.status_code, period, year, actual, overdue: !actual && Boolean(periodEnd(period)) && periodEnd(period) < snapshotDate, operating: u.status_code === 'OPERATING', it, grid, announced});
        });
      });
    });
    return out;
  }
  function annual(rows, metric) {
    const byYear = new Map();
    rows.filter(x => !x.actual && !x.operating && !x.overdue && x.year !== null).forEach(x => {
      if (!byYear.has(x.year)) byYear.set(x.year, {year: x.year, total: 0, known: 0, count: 0});
      const item = byYear.get(x.year);item.count++;
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
  const api = {known, operating, developing, commercial, published, scopeMatch, missing, sumKnown, filterSites, aggregates, schedule, annual, runState, periodEnd};
  root.ManagerData = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof globalThis !== 'undefined' ? globalThis : window);
