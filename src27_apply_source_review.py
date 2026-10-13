#!/usr/bin/env python3
"""Apply reviewed public metadata and field-level evidence in one transaction.

The manifest contains the reviewer's own fact summaries, never article bodies.
Dry run validates references using the live schema and rolls every DB write back.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
from sqlalchemy import create_engine, text
from src04_rss_collector import load_env_file, resolve_database_url
ROOT = Path(__file__).resolve().parent
DEFAULT = ROOT / 'data/reference/source_review_2026-10-13.json'

def target_reviews(manifest):
    """One public document can support separately located centers."""
    for doc in manifest['documents']:
        yield doc
        for target in doc.get('site_reviews', []):
            yield {**doc, **target, 'site_reviews': []}

def validate(manifest):
    checked = date.fromisoformat(manifest['checked_on'])
    if checked > date.today():
        raise ValueError('future review date')
    seen = set()
    codes=set()
    import re
    for s in manifest.get('new_sites', []):
        if not re.fullmatch(r'[A-Z0-9_]{2,30}',s['code']) or s['code'] in codes or not s['name'] or not s['address']:
            raise ValueError('invalid new site')
        codes.add(s['code'])
    for doc in manifest['documents']:
        allowed={'site_code','site_name','facts','capacities','confirm_operating','operating_scope'}
        if any(set(t)-allowed for t in doc.get('site_reviews', [])):raise ValueError('site review cannot override its evidence document')
        parsed = urlparse(doc['url'])
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('invalid public URL')
        if doc['url'] in seen:
            raise ValueError('duplicate document')
        seen.add(doc['url'])
        if doc.get('published_at') and date.fromisoformat(doc['published_at']) > checked:
            raise ValueError('future publication date')
    if any(s['url'] not in seen for s in manifest.get('new_sites', [])):raise ValueError('unverified new site')
    for doc in target_reviews(manifest):
        if doc.get('operating_scope', 'COMMERCIAL') not in {'COMMERCIAL','CLOUD_SELF_USE','ENTERPRISE'}:
            raise ValueError('invalid operating scope')
        if (doc['facts'] or doc['capacities'] or doc['confirm_operating']) and not doc.get('site_code'):
            raise ValueError('missing target site')
        for cap in doc['capacities']:
            if cap['type'] not in {'IT_LOAD_MW','GRID_INTAKE_MW'} or not isinstance(cap['mw'],(float,int)) or not math.isfinite(cap['mw']) or cap['mw'] <= 0:
                raise ValueError('invalid capacity classification')
            if not cap.get('locator'):
                raise ValueError('missing evidence locator')
        for fact in doc['facts']:
            if fact['status'] not in {'CONFIRMED','CANDIDATE'} or fact['origin'] not in {'PRIMARY','REQUOTE'} or not fact['locator']:
                raise ValueError('invalid fact review')
    return manifest

def audit(c, actor, kind, identity, before, after, reason):
    c.execute(text('''INSERT INTO audit_log(actor_id,role_at_action,action,entity_type,entity_id,before_value,after_value,reason,result)
        VALUES(:actor,'REVIEWER','SOURCE_REVIEW',:kind,:identity,CAST(:before AS jsonb),CAST(:after AS jsonb),:reason,'SUCCESS')'''),
        dict(actor=actor,kind=kind,identity=str(identity),before=json.dumps(before,ensure_ascii=False,default=str) if before is not None else None,after=json.dumps(after,ensure_ascii=False,default=str),reason=reason))

def apply_review(c, manifest, storage=None):
    actor=manifest['reviewer'];counts=dict(new_sources=0,new_documents=0,new_facts=0,new_capacities=0,new_projects=0,promoted_sites=0,corrected_capacities=0,new_companies=0,new_relationships=0)
    counts['new_sites']=0
    urls={d['url'] for d in manifest['documents']}
    for s in manifest.get('new_sites', []):
        if s['url'] not in urls:
            raise ValueError('new site lacks reviewed source')
        existing=c.execute(text('SELECT site_id FROM dc_site WHERE site_code=:code'),s).scalar()
        if existing:continue
        sid=c.execute(text("""INSERT INTO dc_site(site_code,site_name,site_name_raw,address_standard,address_raw,sido,sigungu,
            location_precision,coordinate_quality,review_status,public_visible)
            VALUES(:code,:name,:name,:address,:address,:sido,:sigungu,:precision,'U','CONFIRMED',true) RETURNING site_id"""),s).scalar_one()
        audit(c,actor,'SITE',sid,None,s,s['url']);counts['new_sites']+=1
    for s in manifest['sources']:
        existing=c.execute(text('SELECT source_id FROM source_registry WHERE source_code=:code'),s).scalar()
        if existing:
            continue
        sid=c.execute(text('''INSERT INTO source_registry(source_code,source_name,source_type,base_url,default_source_grade,collection_method,collection_interval,terms_review_status,owner_name,note,collection_policy,content_storage_policy,allowed_content_scope,compliance_checked_on,compliance_note)
            VALUES(:code,:name,:type,:url,'B','MANUAL','MONTHLY','LIMITED','MARKET_RESEARCH',:note,'MANUAL_ONLY','URL_ONLY','공개 페이지 사실값과 URL만 저장',:checked,:note) RETURNING source_id'''),{**s,'checked':manifest['checked_on']}).scalar_one()
        audit(c,actor,'SOURCE',sid,None,s,s['url']);counts['new_sources']+=1
    documents={}
    for d in manifest['documents']:
        sid=c.execute(text('SELECT source_id FROM source_registry WHERE source_code=:code'),{'code':d['source_code']}).scalar_one()
        doc=c.execute(text("SELECT document_id,review_status,access_scope FROM evidence_document WHERE source_id=:sid AND canonical_url=:url ORDER BY (access_scope='PUBLIC' AND review_status='CONFIRMED') DESC, created_at DESC, document_id LIMIT 1"),dict(sid=sid,url=d['url'])).mappings().first()
        if doc:
            did=doc['document_id']
        else:
            did=c.execute(text('''INSERT INTO evidence_document(source_id,canonical_url,title,document_type,publisher,published_at,source_grade,access_scope,review_status,reviewed_by,reviewed_at,review_note)
                SELECT :sid,:url,:title,:kind,source_name,:published,default_source_grade,'PUBLIC','CONFIRMED',:actor,NOW(),:note FROM source_registry WHERE source_id=:sid RETURNING document_id'''),dict(sid=sid,url=d['url'],title=d['title'],kind=d['document_type'],published=d['published_at'],actor=actor,note=d['note'] or '공개 원문 확인. 문서 확인과 개별 사실 확정을 구분')).scalar_one()
            audit(c,actor,'EVIDENCE',did,None,{'url':d['url'],'review_status':'CONFIRMED'},d['note'] or d['url']);counts['new_documents']+=1
        if doc and (doc['review_status']!='CONFIRMED' or doc['access_scope']!='PUBLIC'):
            if not d.get('publish_existing'):
                raise ValueError('existing document needs explicit access/review handling')
            c.execute(text("UPDATE evidence_document SET access_scope='PUBLIC',review_status='CONFIRMED',reviewed_by=:actor,reviewed_at=NOW(),review_note=:note WHERE document_id=:did"),dict(actor=actor,note='공개 원문 재검토: '+d['url'],did=did))
            c.execute(text('UPDATE evidence_document_version SET is_current=false WHERE document_id=:did'),{'did':did})
            audit(c,actor,'EVIDENCE',did,dict(doc),{'access_scope':'PUBLIC','review_status':'CONFIRMED'},d['url'])
        vid=c.execute(text('SELECT document_version_id FROM evidence_document_version WHERE document_id=:did AND is_current ORDER BY version_no DESC LIMIT 1'),{'did':did}).scalar()
        if not vid:
            own=json.dumps(d,ensure_ascii=False,sort_keys=True).encode()
            digest=hashlib.sha256(own).hexdigest()
            path=ROOT/'data/raw/source_review'/manifest['checked_on']/(digest+'.json')
            if storage:
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(own)
            vid=c.execute(text('''INSERT INTO evidence_document_version(document_id,version_no,mime_type,content_hash_sha256,raw_storage_path,parser_name,parser_version,extraction_status)
                VALUES(:did,COALESCE((SELECT MAX(version_no)+1 FROM evidence_document_version WHERE document_id=:did),1),'application/json',:hash,:path,'manual-fact-review','1','SUCCESS') RETURNING document_version_id'''),dict(did=did,hash=digest,path=str(path))).scalar_one()
        documents[d['url']]=(did,vid)
    for d in target_reviews(manifest):
        if not d.get('site_code'):
            continue
        site=c.execute(text('SELECT * FROM dc_site WHERE site_code=:code AND record_status=\'ACTIVE\''),{'code':d['site_code']}).mappings().one()
        site_id=site['site_id'];vid=documents[d['url']][1]
        if d.get('site_name') and d['site_name']!=site['site_name']:
            c.execute(text('UPDATE dc_site SET site_name=:name,updated_at=NOW() WHERE site_id=:id'),{'name':d['site_name'],'id':site_id})
            audit(c,actor,'SITE',site_id,{'site_name':site['site_name']},{'site_name':d['site_name']},d['url'])
        if d['confirm_operating']:
            scope=d.get('operating_scope','COMMERCIAL')
            pcode=d['site_code']+'_OP'
            exists=c.execute(text("SELECT project_id FROM dc_project WHERE project_code=:code"),{'code':pcode}).scalar()
            if not exists:
                pid=c.execute(text('''INSERT INTO dc_project(project_code,site_id,project_name,project_type,project_scope,status_code,review_status,public_visible,scope_note)
                    VALUES(:code,:site,:name,:type,'전체 센터','OPERATING','CONFIRMED',true,:note) RETURNING project_id'''),dict(code=pcode,site=site_id,name=site['site_name']+' 운영',type='COLOCATION' if scope=='COMMERCIAL' else 'CLOUD',note=d['url'])).scalar_one()
                audit(c,actor,'PROJECT',pid,None,{'status':'OPERATING'},d['url']);counts['new_projects']+=1
            commercial='IN_SCOPE' if scope=='COMMERCIAL' else 'OUT_OF_SCOPE'
            if site['commercial_scope_status']!=commercial or site['facility_scope']!=scope:
                c.execute(text('''UPDATE dc_site SET commercial_scope_status=:commercial,commercial_model=:model,commercial_review_status='CONFIRMED',commercial_source_url=:url,commercial_scope_note=:note,facility_scope=:scope,facility_review_status='CONFIRMED',facility_source_url=:url,facility_scope_note=:note,updated_at=NOW() WHERE site_id=:site'''),dict(site=site_id,url=d['url'],scope=scope,commercial=commercial,model='COLOCATION' if scope=='COMMERCIAL' else 'UNKNOWN',note='사업자 공식 자료에서 운영 및 시설 범주 확인 · '+manifest['checked_on']))
                audit(c,actor,'SITE',site_id,dict(site),{'commercial_scope_status':commercial,'facility_scope':scope},d['url']);counts['promoted_sites']+=1
        for f in d['facts']:
            value=json.dumps(f['value'],ensure_ascii=False)
            duplicate=c.execute(text('''SELECT f.fact_id FROM extracted_fact f JOIN fact_evidence fe USING(fact_id) WHERE f.scope_type='SITE' AND f.scope_id=:site AND f.field_name=:field AND f.normalized_value=CAST(:value AS jsonb) AND fe.document_version_id=:vid'''),dict(site=str(site_id),field=f['field'],value=value,vid=vid)).scalar()
            if duplicate:
                continue
            typ='BOOLEAN' if isinstance(f['value'],bool) else 'NUMBER' if isinstance(f['value'],(float,int)) else 'TEXT'
            fid=c.execute(text('''INSERT INTO extracted_fact(scope_type,scope_id,field_name,value_type,raw_value_text,normalized_value,normalized_unit,claim_origin,source_grade,review_status,reviewed_by,reviewed_at,review_note)
                VALUES('SITE',:site,:field,:type,:raw,CAST(:value AS jsonb),:unit,:origin,'B',:status,:actor,NOW(),:note) RETURNING fact_id'''),dict(site=str(site_id),field=f['field'],type=typ,raw=str(f['value']),value=value,unit=f['unit'],origin=f['origin'],status=f['status'],actor=actor,note=d['note'] or '공개 원문 사실 확인 '+manifest['checked_on'])).scalar_one()
            c.execute(text('''INSERT INTO fact_evidence(fact_id,document_version_id,evidence_locator,is_primary_evidence) VALUES(:fact,:version,:locator,:primary)'''),dict(fact=fid,version=vid,locator=f['locator'],primary=f['origin']=='PRIMARY'))
            audit(c,actor,'FACT',fid,None,{'field':f['field'],'value':f['value'],'status':f['status']},d['url']);counts['new_facts']+=1
        for cap in d['capacities']:
            duplicate=c.execute(text('''SELECT capacity_id FROM capacity_snapshot WHERE scope_type='SITE' AND scope_id=:site AND capacity_type_code=:type AND normalized_value_mw=:mw AND document_url=:url AND review_status='CONFIRMED' ''') ,dict(site=site_id,type=cap['type'],mw=cap['mw'],url=d['url'])).scalar()
            if duplicate:
                continue
            cid=c.execute(text('''INSERT INTO capacity_snapshot(scope_type,scope_id,capacity_type_code,raw_value,raw_unit,normalized_value_mw,capacity_stage,measurement_basis,published_at,document_url,evidence_location,review_status,note)
                VALUES('SITE',:site,:type,:mw,'MW',:mw,'OPERATING','PUBLISHED_CAPACITY',:published,:url,:locator,'CONFIRMED',:note) RETURNING capacity_id'''),dict(site=site_id,type=cap['type'],mw=cap['mw'],published=d['published_at'],url=d['url'],locator=cap['locator'],note='운영 시설의 발표 총용량 · 실측 부하/입주/가용 용량 아님. '+(d['note'] or '확인일 '+manifest['checked_on']))).scalar_one()
            audit(c,actor,'CAPACITY',cid,None,cap,d['url']);counts['new_capacities']+=1
    for relation in manifest.get('relationships',[]):
        company=c.execute(text('SELECT company_id FROM company WHERE standard_name=:name ORDER BY company_id LIMIT 1'),relation).scalar()
        if not company:
            company=relation['company_id']
            c.execute(text("INSERT INTO company(company_id,standard_name,official_url,review_status,note) VALUES(:company_id,:name,:url,'CONFIRMED','공식 서비스 운영 주체. 브랜드명과 법인 실명 구분')"),relation)
            audit(c,actor,'COMPANY',company,None,relation,relation['url']);counts['new_companies']+=1
        site=c.execute(text('SELECT site_id FROM dc_site WHERE site_code=:site_code'),relation).scalar_one()
        for role in relation['roles']:
            params=dict(company=company,site=site,role=role,url=relation['url'])
            exists=c.execute(text("SELECT participation_id FROM company_participation WHERE company_id=:company AND scope_type='SITE' AND scope_id=:site AND role_code=:role AND review_status='CONFIRMED' AND public_visible"),params).scalar()
            if not exists:
                pid=c.execute(text("INSERT INTO company_participation(company_id,scope_type,scope_id,role_code,review_status,public_visible,evidence_url) VALUES(:company,'SITE',:site,:role,'CONFIRMED',true,:url) RETURNING participation_id"),params).scalar_one()
                audit(c,actor,'PARTICIPATION',pid,None,{'company':company,'role':role},relation['url']);counts['new_relationships']+=1
    for change in manifest.get('corrections',[]):
        affected=c.execute(text("""SELECT cs.* FROM capacity_snapshot cs
            WHERE cs.capacity_type_code=:type AND cs.document_url=:old_url
            AND ((cs.scope_type='SITE' AND cs.scope_id=(SELECT site_id FROM dc_site WHERE site_code=:site_code))
            OR (cs.scope_type='PROJECT' AND cs.scope_id IN(SELECT p.project_id FROM dc_project p JOIN dc_site s USING(site_id) WHERE s.site_code=:site_code)))"""),change).mappings().all()
        for old in affected:
            if old['capacity_type_code']==change['new_type'] and old['document_url']==change['new_url'] and old['review_status']==change['review_status'] and old['aggregation_excluded']==change['exclude']:
                continue
            c.execute(text("""UPDATE capacity_snapshot SET capacity_type_code=:new_type,document_url=:new_url,review_status=:review_status,aggregation_excluded=:exclude,exclusion_reason=:reason,note=:reason,updated_at=NOW() WHERE capacity_id=:id"""),{**change,'id':old['capacity_id']})
            audit(c,actor,'CAPACITY',old['capacity_id'],dict(old),change,change['reason'])
            counts['corrected_capacities']+=1
    return counts

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest',nargs='?',type=Path,default=DEFAULT);p.add_argument('--apply',action='store_true');args=p.parse_args()
    manifest=validate(json.loads(args.manifest.read_text()))
    load_env_file();engine=create_engine(resolve_database_url())
    try:
        with engine.connect() as c:
            tx=c.begin()
            try:
                # Prevent concurrent daily publishes and imports from duplicating review records.
                c.execute(text('SELECT pg_advisory_xact_lock(270013)'))
                counts=apply_review(c,manifest,storage=args.apply)
                if args.apply: tx.commit()
                else: tx.rollback()
            except Exception:
                tx.rollback();raise
        print(json.dumps({'applied':args.apply,**counts},ensure_ascii=False))
    finally:engine.dispose()
    return 0
if __name__=='__main__':raise SystemExit(main())
