#!/usr/bin/env python3
"""Apply a reviewed development manifest while preserving unknown RFS and IT MW."""
import argparse,json,re,math
from pathlib import Path
from sqlalchemy import create_engine,text
from src04_rss_collector import load_env_file,resolve_database_url
from src27_apply_source_review import validate,apply_review,audit
DEFAULT=Path(__file__).resolve().parent/'data/reference/paju_review_2026-10-13.json'
CODE=re.compile(r'^[A-Z0-9_]{2,30}$')

def validate_period(period,precision):
    patterns={'DAY':r'\d{4}-\d{2}-\d{2}','MONTH':r'\d{4}-(0[1-9]|1[0-2])','QUARTER':r'\d{4}-Q[1-4]','YEAR':r'\d{4}'}
    if period is None and precision in {None,'UNKNOWN'}:return
    if precision not in patterns or not isinstance(period,str) or not re.fullmatch(patterns[precision],period):raise ValueError('invalid schedule precision')
    if precision=='DAY':
        from datetime import date
        date.fromisoformat(period)

def validate_development(m):
    validate(m)
    urls={d['url'] for d in m['documents']}
    for site in m['development_sites']:
        if site['url'] not in urls or not CODE.fullmatch(site['site_code']):raise ValueError('unverified site')
        codes={p['code'] for p in site['projects']}
        for project in site['projects']:
            if not CODE.fullmatch(project['code']) or project['url'] not in urls or project['status'] not in {'IDEA','SITE_SECURED','PERMITTING','POWER_SECURED','CONSTRUCTION','READY'}:raise ValueError('invalid development project')
            validate_period(project.get('planned_rfs_period'),project.get('planned_rfs_precision'))
        for phase in site['phases']:
            if phase['project_code'] not in codes or not CODE.fullmatch(phase['code']) or phase['url'] not in urls:raise ValueError('invalid phase')
            validate_period(phase.get('planned_completion_period'),phase.get('planned_completion_precision'))
            validate_period(phase.get('planned_rfs_period'),phase.get('planned_rfs_precision'))
        for cap in site['capacities']:
            if cap['url'] not in urls or cap['type'] not in {'GRID_INTAKE_MW','IT_LOAD_MW'} or not math.isfinite(cap['mw']) or cap['mw']<=0 or cap['scope_type']!='PROJECT' or cap['scope_code'] not in codes or cap['stage'] not in {'ANNOUNCED','SECURED','DESIGNED','UNDER_CONSTRUCTION'}:raise ValueError('invalid scoped capacity')
    return m

def apply_development(c,m,storage=False):
    count=apply_review(c,m,storage=storage);count.update(updated_development_sites=0,new_phases=0)
    actor=m['reviewer']
    for plan in m['development_sites']:
        site=dict(c.execute(text('SELECT * FROM dc_site WHERE site_code=:site_code AND record_status=\'ACTIVE\''),plan).mappings().one())
        desired=dict(site_name=plan['site_name'],address_standard=plan['address'],address_raw=plan['address'],sido=plan['sido'],sigungu=plan['sigungu'],commercial_model=plan['commercial_model'],commercial_scope_status='IN_SCOPE',commercial_review_status='CONFIRMED',commercial_source_url=plan['url'],commercial_scope_note=plan['note'],facility_scope='COMMERCIAL',facility_review_status='CONFIRMED',facility_source_url=plan['url'],facility_scope_note=plan['note'],review_status='CONFIRMED',public_visible=True)
        if any(site[k]!=v for k,v in desired.items()):
            assignments=','.join(k+'=:'+k for k in desired)
            if site['address_standard']!=plan['address']:
                assignments+=",geom=NULL,coordinate_quality='U',location_precision=:precision"
                desired['precision']=plan.get('location_precision','PARCEL')
            c.execute(text('UPDATE dc_site SET '+assignments+' WHERE site_id=:id'),{**desired,'id':site['site_id']})
            audit(c,actor,'SITE',site['site_id'],site,desired,plan['url']);count['updated_development_sites']+=1
        projects={}
        for p in plan['projects']:
            pid=c.execute(text('SELECT project_id FROM dc_project WHERE project_code=:code AND site_id=:site'),{**p,'site':site['site_id']}).scalar()
            if pid is None:
                pid=c.execute(text("INSERT INTO dc_project(project_code,site_id,project_name,project_type,project_scope,status_code,review_status,public_visible,scope_note,planned_rfs_period,planned_rfs_precision) VALUES(:code,:site,:name,:type,'WHOLE_SITE',:status,'CONFIRMED',true,:note,:planned_rfs_period,:planned_rfs_precision) RETURNING project_id"),{'planned_rfs_period':None,'planned_rfs_precision':None,**p,'site':site['site_id']}).scalar_one()
                audit(c,actor,'PROJECT',pid,None,p,p['url']);count['new_projects']+=1
            projects[p['code']]=pid
        for ph in plan['phases']:
            exists=c.execute(text('SELECT phase_id FROM project_phase WHERE phase_code=:code AND project_id=:project'),{**ph,'project':projects[ph['project_code']]}).scalar()
            if exists is None:
                pid=c.execute(text("INSERT INTO project_phase(phase_code,project_id,phase_name,phase_order,scope_description,status_code,review_status,planned_completion_period,planned_completion_precision,planned_rfs_period,planned_rfs_precision) VALUES(:code,:project,:name,:order,:note,:status,'CONFIRMED',:planned_completion_period,:planned_completion_precision,:planned_rfs_period,:planned_rfs_precision) RETURNING phase_id"),{'planned_completion_period':None,'planned_completion_precision':None,'planned_rfs_period':None,'planned_rfs_precision':None,**ph,'project':projects[ph['project_code']]}).scalar_one()
                audit(c,actor,'PHASE',pid,None,ph,ph['url']);count['new_phases']+=1
        for cap in plan['capacities']:
            params={**cap,'scope_id':projects[cap['scope_code']]}
            existing=c.execute(text("SELECT capacity_id FROM capacity_snapshot WHERE scope_type=:scope_type AND scope_id=:scope_id AND capacity_type_code=:type AND normalized_value_mw=:mw AND document_url=:url AND capacity_stage=:stage AND review_status='CONFIRMED'"),params).scalar()
            if existing is None:
                cid=c.execute(text("INSERT INTO capacity_snapshot(scope_type,scope_id,capacity_type_code,raw_value,raw_unit,normalized_value_mw,capacity_stage,measurement_basis,published_at,document_url,evidence_location,review_status,note) VALUES(:scope_type,:scope_id,:type,:mw,'MW',:mw,:stage,'PUBLISHED_CAPACITY',:published_at,:url,:locator,'CONFIRMED',:note) RETURNING capacity_id"),params).scalar_one()
                audit(c,actor,'CAPACITY',cid,None,cap,cap['url']);count['new_capacities']+=1
    return count

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest',nargs='?',type=Path,default=DEFAULT);p.add_argument('--apply',action='store_true');args=p.parse_args()
    m=validate_development(json.loads(args.manifest.read_text()));load_env_file();engine=create_engine(resolve_database_url())
    try:
        with engine.connect() as c:
            tx=c.begin()
            try:
                c.execute(text('SELECT pg_advisory_xact_lock(270013)'));counts=apply_development(c,m,args.apply)
                if args.apply:tx.commit()
                else:tx.rollback()
            except Exception:tx.rollback();raise
        print(json.dumps({'applied':args.apply,**counts},ensure_ascii=False))
    finally:engine.dispose()
    return 0
if __name__=='__main__':raise SystemExit(main())
