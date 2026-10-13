const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = process.argv[2];
if (!path) throw Error('Pass the manager-core.js path');
const context = {module:{exports:{}}, console};
vm.runInNewContext(fs.readFileSync(path,'utf8'),context);
const C=context.module.exports;
const base={site_code:'A',site_name:'센터 A',commercial_scope_status:'IN_SCOPE',commercial_review_status:'CONFIRMED',public_visible:true,review_status:'CONFIRMED',lifecycle_group:'MIXED',operating_it_load_mw:12,development_it_load_mw:16};
const candidate={...base,site_code:'B',public_visible:false,review_status:'NEEDS_EVIDENCE',operating_it_load_mw:500};
const selfUse={...base,site_code:'C',commercial_scope_status:'OUT_OF_SCOPE',facility_scope:'CLOUD_SELF_USE',operating_it_load_mw:600};
const result=C.aggregates([base,candidate,selfUse]);
assert.equal(result.eligible.length,1);
assert.equal(result.op.length,1);assert.equal(result.dev.length,1);
assert.equal(result.operating.value,12);assert.equal(result.development.value,16);
assert.equal(C.sumKnown([{}],'value').value,null);
assert.equal(C.sumKnown([{value:0}],'value').value,0);
assert.equal(C.filterSites([base,selfUse],{scope:'CLOUD_SELF_USE'}).length,1);
const data={generated_at:'2026-10-13',details:{A:{projects:[{project_code:'P',planned_rfs_period:'2028 Q2'}],phases:[{project_code:'P',phase_code:'PH1',phase_name:'1차',planned_rfs_date:'2028-04-01'}],capacities:[
 {scope_type:'PROJECT',project_code:'P',capacity_type_code:'IT_LOAD_MW',normalized_value_mw:100},
 {scope_type:'PHASE',phase_code:'PH1',capacity_type_code:'GRID_INTAKE_MW',normalized_value_mw:50},
 {scope_type:'PHASE',phase_code:'PH1',capacity_type_code:'IT_LOAD_MW',normalized_value_mw:20,published_at:'2025-01-01'},
 {scope_type:'PHASE',phase_code:'PH1',capacity_type_code:'IT_LOAD_MW',normalized_value_mw:24,published_at:'2026-01-01'},
 {scope_type:'PHASE',phase_code:'PH1',capacity_type_code:'IT_LOAD_MW',normalized_value_mw:99,published_at:'2026-09-01',effective_to:'2026-09-10'},
 {scope_type:'PHASE',phase_code:'PH1',capacity_type_code:'IT_LOAD_MW',normalized_value_mw:80,aggregation_excluded:true}
]}}};
const rows=C.schedule(data,[base,candidate,selfUse]);
assert.equal(rows.length,1);assert.equal(rows[0].it,24);assert.equal(rows[0].grid,50);
assert.equal(C.annual(rows,'it')[0].total,24);
assert.equal(C.annual([{year:2028,it:20,actual:true},{year:2028,it:30,actual:false,operating:true}],'it').length,0);
assert.equal(C.annual([{year:2028,it:null,actual:false}],'it')[0].known,0);
assert.equal(C.periodEnd('2028 Q2'),'2028-06-30');
assert.equal(C.periodEnd('2028-Q2'),'2028-06-30');
assert.equal(C.periodEnd('2026'),'2026-12-31');
assert.equal(C.annual([{year:2024,it:90,actual:false,overdue:true}],'it').length,0);
assert.equal(C.runState({job_name:'RSS_DAILY',run_status:'SUCCESS',finished_at:'2026-10-12T00:00:00Z'},Date.parse('2026-10-13T00:00:00Z')).css,'dev');
console.log('PASS: mixed campus, scope/privacy, unknown capacity, phase/parent deduplication, capacity history, expired/excluded values, actual/operating RFS exclusion, stale collection');
