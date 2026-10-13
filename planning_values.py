"""Working assumptions never change the verified source records."""
from __future__ import annotations
import json,math,re
from datetime import date
from urllib.parse import urlparse,parse_qs
from sqlalchemy import text
from src27_apply_source_review import audit

FIELDS={'IT_LOAD_MW','GRID_INTAKE_MW','RFS_PERIOD','COMPLETION_PERIOD','STATUS_CODE','ADDRESS','OPERATOR_NAME','PUE'}
BASES={'ANNOUNCED','ESTIMATED','MANUAL','MANUAL_CONFIRMED'}
STAGES={'OPERATING','DEVELOPMENT','MIXED','UNKNOWN','IDEA','SITE_SECURED','PERMITTING','POWER_SECURED','CONSTRUCTION','READY','ON_HOLD','CANCELLED'}
class PlanningConflict(ValueError):pass

def validate_value(d):
    if not isinstance(d,dict):raise ValueError('invalid record')
    if any(not isinstance(d.get(k),str) for k in ['field_name','scope_type','basis','bucket']):raise ValueError('invalid classification type')
    if d.get('field_name') not in FIELDS or d.get('scope_type') not in {'SITE','PROJECT','PHASE'}:raise ValueError('invalid field or scope')
    if d.get('basis') not in BASES or d.get('bucket') not in {'GENERAL','OPERATING','DEVELOPMENT'}:raise ValueError('invalid classification')
    for key in ['site_code','scope_code']:
        if not isinstance(d.get(key),str) or not re.fullmatch(r'[A-Z0-9_]{2,30}',d[key]):raise ValueError('invalid code')
    if not isinstance(d.get('reviewer'),str) or not 1<=len(d['reviewer'].strip())<=100:raise ValueError('missing editor')
    if not isinstance(d.get('method'),str) or not 1<=len(d['method'].strip())<=2000:raise ValueError('missing method')
    if type(d.get('expected_version')) is not int or d['expected_version']<0:raise ValueError('missing version')
    if type(d.get('public_visible')) is not bool or type(d.get('active',True)) is not bool:raise ValueError('invalid visibility')
    if d.get('source_url') is not None and not isinstance(d['source_url'],str):raise ValueError('invalid source type')
    url=d.get('source_url') or None
    if url:
        p=urlparse(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password or len(url)>2000 or any(re.search('token|password|secret|api.?key',k,re.I) for k in parse_qs(p.query)):raise ValueError('invalid source URL')
    v=d.get('value');field=d['field_name'];numeric=field in {'IT_LOAD_MW','GRID_INTAKE_MW','PUE'}
    low=d.get('low_value');high=d.get('high_value')
    if numeric:
        if type(v) not in {float,int} or not math.isfinite(v) or v<0 or v>100000:raise ValueError('invalid numeric value')
        if field=='PUE' and not 1<=v<=5:raise ValueError('invalid PUE')
        if field=='PUE' and d['bucket']!='GENERAL':raise ValueError('PUE bucket')
        if field!='PUE' and d['bucket']=='GENERAL':raise ValueError('capacity requires stage bucket')
        for n in [low,high]:
            if n is not None and (type(n) not in {float,int} or not math.isfinite(n) or n<0):raise ValueError('invalid interval')
        if low is not None and low>v or high is not None and high<v:raise ValueError('value outside interval')
    else:
        if not isinstance(v,str) or not v.strip() or len(v)>500 or low is not None or high is not None:raise ValueError('invalid text value')
        if d['bucket']!='GENERAL':raise ValueError('text field bucket')
        if field in {'RFS_PERIOD','COMPLETION_PERIOD'}:
            v=re.sub(r'^(\d{4})[\s-]*[Qq]([1-4])$',r'\1-Q\2',v.strip())
            if not re.fullmatch(r'\d{4}(-Q[1-4]|-(0[1-9]|1[0-2])(-\d{2})?)?',v):raise ValueError('invalid period')
            if not 1900<=int(v[:4])<=2200:raise ValueError('invalid year')
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}',v):date.fromisoformat(v)
        if field=='STATUS_CODE':
            allowed={'OPERATING','DEVELOPMENT','MIXED','UNKNOWN','ON_HOLD'} if d['scope_type']=='SITE' else STAGES-{'DEVELOPMENT','MIXED','UNKNOWN'}
            if v not in allowed:raise ValueError('invalid stage for scope')
        if field in {'ADDRESS','OPERATOR_NAME'} and d['scope_type']!='SITE':raise ValueError('site field scope')
    return {**d,'value':v,'source_url':url,'active':d.get('active',True),'low_value':low,'high_value':high}

def target(c,d):
    site=c.execute(text("SELECT site_id,public_visible,review_status FROM dc_site WHERE site_code=:site_code AND record_status='ACTIVE'"),d).mappings().one_or_none()
    if not site:raise ValueError('site missing')
    if d['scope_type']=='SITE':
        if d['scope_code']!=d['site_code']:raise ValueError('site scope mismatch')
    else:
        q=("SELECT project_id FROM dc_project WHERE project_code=:scope_code AND site_id=:site AND record_status='ACTIVE'" if d['scope_type']=='PROJECT' else "SELECT ph.phase_id FROM project_phase ph JOIN dc_project p USING(project_id) WHERE ph.phase_code=:scope_code AND p.site_id=:site AND ph.record_status='ACTIVE' AND p.record_status='ACTIVE'")
        if not c.execute(text(q),{**d,'site':site['site_id']}).first():raise ValueError('scope does not belong to site')
    return site['site_id']

def write_value(c,raw):
    d=validate_value(raw);d['site']=target(c,d)
    identity='|'.join(str(d[k]) for k in ['site','scope_type','scope_code','field_name','bucket'])
    c.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:key,0))'),{'key':identity})
    old=c.execute(text('SELECT * FROM planning_value WHERE site_id=:site AND scope_type=:scope_type AND scope_code=:scope_code AND field_name=:field_name AND bucket=:bucket FOR UPDATE'),d).mappings().first()
    if (old['version'] if old else 0)!=d['expected_version']:raise PlanningConflict('value changed')
    fields='value=CAST(:json AS jsonb),low_value=:low_value,high_value=:high_value,basis=:basis,method=:method,source_url=:source_url,public_visible=:public_visible,active=:active,updated_by=:reviewer,updated_at=NOW()'
    params={**d,'json':json.dumps(d['value'],ensure_ascii=False)}
    if old:
        row=c.execute(text('UPDATE planning_value SET '+fields+',version=version+1 WHERE planning_id=:id RETURNING *'),{**params,'id':old['planning_id']}).mappings().one()
    else:
        row=c.execute(text('''INSERT INTO planning_value(site_id,scope_type,scope_code,field_name,bucket,value,low_value,high_value,basis,method,source_url,public_visible,active,updated_by)
            VALUES(:site,:scope_type,:scope_code,:field_name,:bucket,CAST(:json AS jsonb),:low_value,:high_value,:basis,:method,:source_url,:public_visible,:active,:reviewer) RETURNING *'''),params).mappings().one()
    audit(c,d['reviewer'],'PLANNING_VALUE',row['planning_id'],dict(old) if old else None,dict(row),'담당자 작업값 수정: '+d['method'])
    return {**dict(row),'site_code':d['site_code']}

def save_value(engine,d):
    with engine.begin() as c:return write_value(c,d)

def list_values(engine,public_only=True,site_code=None):
    conditions=["s.record_status='ACTIVE'"]
    if public_only:
        conditions.extend(["pv.active","pv.public_visible","s.public_visible","s.review_status='CONFIRMED'",
            "(pv.scope_type='SITE' OR pv.scope_type='PROJECT' AND EXISTS(SELECT 1 FROM dc_project p WHERE p.site_id=s.site_id AND p.project_code=pv.scope_code AND p.public_visible AND p.review_status='CONFIRMED' AND p.record_status='ACTIVE') OR pv.scope_type='PHASE' AND EXISTS(SELECT 1 FROM project_phase ph JOIN dc_project p USING(project_id) WHERE p.site_id=s.site_id AND ph.phase_code=pv.scope_code AND p.public_visible AND p.review_status='CONFIRMED' AND ph.review_status='CONFIRMED' AND p.record_status='ACTIVE' AND ph.record_status='ACTIVE'))"])
    if site_code:conditions.append('s.site_code=:code')
    with engine.connect() as c:
        fields="pv.planning_id,pv.scope_type,pv.scope_code,pv.field_name,pv.bucket,pv.value,pv.low_value,pv.high_value,pv.basis,pv.method,pv.source_url,pv.public_visible,pv.active,pv.version,pv.updated_at,s.site_code"+('' if public_only else ',pv.updated_by')
        rows=[dict(r) for r in c.execute(text('SELECT '+fields+' FROM planning_value pv JOIN dc_site s USING(site_id) WHERE '+' AND '.join(conditions)+' ORDER BY s.site_code,pv.scope_type,pv.scope_code,pv.field_name'),{'code':site_code}).mappings()]
        for row in rows:row['planning_id']=str(row['planning_id'])
        return rows

def planning_summary(engine):
    rows=list_values(engine)
    with engine.connect() as c:
        sites=[dict(r) for r in c.execute(text("""SELECT s.site_code,v.operating_it_load_mw,v.development_it_load_mw
            FROM dc_site s JOIN v_site_map v USING(site_id) WHERE s.public_visible AND s.review_status='CONFIRMED'
            AND s.record_status='ACTIVE' AND s.commercial_scope_status='IN_SCOPE' AND s.commercial_review_status='CONFIRMED'""")).mappings()]
    verified={s['site_code'] for s in sites if s['operating_it_load_mw'] is not None or s['development_it_load_mw'] is not None}
    eligible={s['site_code'] for s in sites}
    working={r['site_code'] for r in rows if r['field_name']=='IT_LOAD_MW'} & eligible
    return {'public_working_values':len(rows),'centers_with_working_values':len({r['site_code'] for r in rows}),
            'commercial_centers':len(sites),'verified_it_centers':len(verified),'working_it_centers':len(verified|working),
            'basis_counts':{b:sum(r['basis']==b for r in rows) for b in sorted(BASES)}}
