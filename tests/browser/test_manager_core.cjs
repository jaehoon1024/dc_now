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

const phaseCompletion={generated_at:'2026-10-13',details:{A:{projects:[{project_code:'PD'}],phases:[{project_code:'PD',phase_code:'P1',status_code:'CONSTRUCTION',planned_completion_period:'2027-06'}],capacities:[{scope_type:'PROJECT',project_code:'PD',capacity_type_code:'GRID_INTAKE_MW',normalized_value_mw:200}]}}};
const completion=C.schedule(phaseCompletion,[base]);
assert.equal(completion[0].period,'');assert.equal(completion[0].year,null);assert.equal(completion[0].completion_period,'2027-06');assert.equal(completion[0].grid,null);assert.equal(C.annual(completion,'grid').length,0);

const planning={generated_at:'2026-10-13',sites:[{...base,lifecycle_group:'DEVELOPMENT',operating_it_load_mw:null,development_it_load_mw:null}],details:{A:{projects:[{project_code:'PD',status_code:'CONSTRUCTION'}],phases:[{project_code:'PD',phase_code:'P1',status_code:'CONSTRUCTION',planned_completion_period:'2027-06'}],capacities:[]}},planning_values:[
 {site_code:'A',scope_type:'SITE',scope_code:'A',field_name:'IT_LOAD_MW',bucket:'DEVELOPMENT',value:100,low_value:80,high_value:120,basis:'ESTIMATED',active:true},
 {site_code:'A',scope_type:'PHASE',scope_code:'P1',field_name:'IT_LOAD_MW',bucket:'DEVELOPMENT',value:40,basis:'ANNOUNCED',active:true},
 {site_code:'A',scope_type:'PHASE',scope_code:'P1',field_name:'RFS_PERIOD',bucket:'GENERAL',value:'2027-Q4',basis:'ESTIMATED',active:true}
]};
const work=C.prepare(planning,true),strict=C.prepare(planning,false);
assert.equal(work.sites[0].development_it_load_mw,100);assert.equal(work.details.A.development_it_load_mw,100);
assert.equal(strict.sites[0].development_it_load_mw,null);assert.equal(planning.sites[0].development_it_load_mw,null);
assert.equal(C.schedule(work,work.sites)[0].it,40);assert.equal(C.schedule(work,work.sites)[0].period,'2027-Q4');
assert.equal(C.annual(C.schedule(work,work.sites),'it')[0].total,40);assert.equal(C.sumKnown(work.sites,'development_it_load_mw').low,80);
const fresh={...planning,sites:[{...planning.sites[0],development_it_load_mw:90}]};assert.equal(C.prepare(fresh,true).sites[0].development_it_load_mw,90);
const correction={...planning.planning_values[0],value:110,basis:'MANUAL',draft:true};assert.equal(C.prepare(fresh,true,[correction]).sites[0].development_it_load_mw,110);
assert.equal(C.prepare(fresh,true,[{...correction,active:false}]).sites[0].development_it_load_mw,90);
assert.equal(C.periodEnd('2027-02-29'),null);assert.equal(C.periodEnd('2028-02-29'),'2028-02-29');assert.equal(C.periodEnd('2028-13'),null);
const held=C.prepare(planning,true,[{site_code:'A',scope_type:'SITE',scope_code:'A',field_name:'STATUS_CODE',bucket:'GENERAL',value:'ON_HOLD',basis:'MANUAL',active:true}]);assert.equal(C.annual(C.schedule(held,held.sites),'it').length,0);
console.log('PASS: estimates versus verified values, manual priority, immutable source data, withdrawal, phase/campus separation and real dates');
