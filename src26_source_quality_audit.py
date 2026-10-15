#!/usr/bin/env python3
"""Audit source contribution and public center coverage without reading secrets."""
from __future__ import annotations
import argparse,json
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine,text
from src04_rss_collector import load_env_file,resolve_database_url
ROOT=Path(__file__).resolve().parent
RESEARCH={'CBRE_DC_KR','CUSHMAN_DC_KR','JLL_DC_KR','SAVILLS_DC_KR','RSQUARE_DC_KR'}
ALIASES=ROOT/'data/reference/discovery_aliases.json'

DISCOVERY_QUERY = """
 WITH titles AS MATERIALIZED (
  SELECT document_id,published_at,
   regexp_replace(lower(title),'[[:space:][:punct:]]','','g') AS normalized_title
  FROM evidence_document WHERE record_status='ACTIVE' AND access_scope='PUBLIC'
  AND COALESCE(published_at,created_at)>=CURRENT_DATE-INTERVAL '3 years'
  AND title ~* '데이터[[:space:]]*센터|data[[:space:]]*cent(er|re)|AIDC|IDC'
 ), candidates AS MATERIALIZED (
  SELECT s.site_id,s.site_code,s.site_name,s.commercial_scope_status,
   regexp_replace(lower(s.site_name),'데이터[[:space:]]*센터|data[[:space:]]*cent(er|re)|센터|[[:space:][:punct:]]','','g') AS stem,
   (SELECT count(*) FROM dc_project p WHERE p.site_id=s.site_id AND p.public_visible
    AND p.review_status='CONFIRMED' AND p.record_status='ACTIVE') AS project_count
  FROM dc_site s WHERE s.record_status='ACTIVE' AND s.public_visible
   AND s.facility_scope NOT IN ('ENTERPRISE','CLOUD_SELF_USE','PUBLIC')
 )
 SELECT s.site_code,s.site_name,s.commercial_scope_status,s.project_count,
  count(DISTINCT n.document_id) AS mention_count,max(n.published_at) AS latest_published_at
 FROM candidates s
 LEFT JOIN jsonb_to_recordset(CAST(:aliases AS jsonb)) AS a(site_code text,title_pattern text) ON a.site_code=s.site_code
 JOIN titles n ON (length(s.stem)>=6 AND position(s.stem in n.normalized_title)>0)
   OR (a.title_pattern IS NOT NULL AND n.normalized_title ~ a.title_pattern)
 WHERE s.commercial_scope_status='REVIEW_REQUIRED' OR s.project_count=0
 GROUP BY s.site_id,s.site_code,s.site_name,s.commercial_scope_status,s.project_count
 HAVING count(DISTINCT n.document_id)>=3
 ORDER BY count(DISTINCT n.document_id) DESC,s.site_code LIMIT 30
"""

def discovery_gaps(connection):
    config=json.loads(ALIASES.read_text()) if ALIASES.exists() else {'aliases':[],'open_reviews':[]}
    rows=[dict(r) for r in connection.execute(text(DISCOVERY_QUERY),{'aliases':json.dumps(config['aliases'],ensure_ascii=False)}).mappings()]
    for row in rows:
        issues=[]
        if row['commercial_scope_status']=='REVIEW_REQUIRED':issues.append('상용 범주 미검증')
        if not row['project_count']:issues.append('확정 프로젝트 미연계')
        row['issue']=' · '.join(issues)
    for review in config.get('open_reviews',[]):
        site=connection.execute(text("""SELECT s.site_code,s.site_name,s.commercial_scope_status,
            (SELECT count(*) FROM dc_project p WHERE p.site_id=s.site_id AND p.public_visible AND p.review_status='CONFIRMED' AND p.record_status='ACTIVE') AS project_count
            FROM dc_site s WHERE s.site_code=:site_code AND s.public_visible AND s.record_status='ACTIVE'"""),review).mappings().first()
        if site:
            row=next((r for r in rows if r['site_code']==review['site_code']),None)
            if row:row['issue']+=' · '+review['issue']
            else:rows.append({**dict(site),'mention_count':review['document_count'],'latest_published_at':review['published_at'],'issue':review['issue']})
    return rows

def group(row):
    if row['source_code'].endswith('_LICENSED'):return '유료 전문 데이터'
    if row['source_code']=='KB_DC_RESEARCH':return '증권·금융기관 리서치'
    if row['source_code'] in RESEARCH:return '컨설팅·부동산 리서치'
    if row['source_type'] in {'GOVERNMENT','REGULATOR'}:return '공공·공시'
    if row['source_type']=='COMPANY':return '사업자 공식자료'
    if row['source_code']=='GOOGLE_NEWS_DC':return '뉴스 탐색'
    if row['source_type']=='NEWS':return '일반·전문 뉴스'
    return '전문기관·참고 원장'

def summarize(rows):
    total=sum(r['documents'] for r in rows)
    aggregator=sum(r['aggregator_urls'] for r in rows)
    return dict(registered_sources=len(rows),contributing_sources=sum(r['documents']>0 for r in rows),registered_only_sources=sum(r['documents']==0 for r in rows),total_documents=total,aggregator_documents=aggregator,aggregator_share_pct=round(100*aggregator/total,2) if total else None)

def assess(engine):
    from planning_values import planning_summary
    with engine.connect() as c:
        rows=[dict(r) for r in c.execute(text('''SELECT sr.source_code,sr.source_name,sr.source_type,sr.base_url,sr.collection_method,sr.collection_policy,sr.active,
            COUNT(ed.document_id)::int AS documents,
            COUNT(ed.document_id) FILTER(WHERE ed.created_at>=CURRENT_TIMESTAMP-INTERVAL '7 days')::int AS documents_last_7_days,
            COUNT(ed.document_id) FILTER(WHERE ed.review_status='CONFIRMED' AND ed.access_scope='PUBLIC')::int AS public_confirmed,
            COUNT(ed.document_id) FILTER(WHERE ed.canonical_url LIKE 'https://news.google.com/%')::int AS aggregator_urls,
            MAX(ed.created_at) AS latest_imported_at
            FROM source_registry sr LEFT JOIN evidence_document ed ON ed.source_id=sr.source_id AND ed.record_status='ACTIVE'
            GROUP BY sr.source_id ORDER BY COUNT(ed.document_id) DESC,sr.source_code''')).mappings()]
        from source_contribution import enrich_rows
        enrich_rows(rows,c)
        coverage=dict(c.execute(text('''SELECT COUNT(*) AS commercial_centers,
            COUNT(*) FILTER(WHERE v.operating_it_load_mw IS NOT NULL OR v.development_it_load_mw IS NOT NULL) AS centers_with_it_mw,
            COUNT(*) FILTER(WHERE v.operating_grid_intake_mw IS NOT NULL OR v.development_grid_intake_mw IS NOT NULL) AS centers_with_grid_mw,
            COUNT(*) FILTER(WHERE v.lifecycle_group='UNKNOWN') AS centers_with_unknown_stage,
            COUNT(*) FILTER(WHERE s.geom IS NOT NULL AND s.coordinate_quality IN ('A','B')) AS centers_with_verified_coordinates
            FROM dc_site s JOIN v_site_map v USING(site_id)
            WHERE s.record_status='ACTIVE' AND s.review_status='CONFIRMED' AND s.public_visible
            AND s.commercial_scope_status='IN_SCOPE' AND s.commercial_review_status='CONFIRMED' ''')).mappings().one())
        capacity_links=dict(c.execute(text('''SELECT COUNT(*) AS confirmed_capacity_records,
            COUNT(*) FILTER(WHERE EXISTS(SELECT 1 FROM evidence_document ed WHERE ed.canonical_url=cs.document_url AND ed.access_scope='PUBLIC' AND ed.review_status='CONFIRMED' AND ed.record_status='ACTIVE')) AS records_with_public_document
            FROM capacity_snapshot cs WHERE cs.review_status='CONFIRMED' ''')).mappings().one())
    for r in rows:
        r['group']=group(r)
        r['acquisition_status']='계약 필요 · 미취득' if r['source_code'].endswith('_LICENSED') else '등록만 · 문서 미확보' if not r['documents'] else '수동 근거 확보' if r['collection_policy'] in {'MANUAL_ONLY','BLOCKED'} else '문서 확보 · 수집 연계'
    for r in rows:r['acquisition_status']=r['connection_label']
    manifests=[json.loads(path.read_text()) for path in sorted((ROOT/'data/reference').glob('*review_*.json'))]
    reference_docs={doc['url']:doc for manifest in manifests for doc in manifest['documents']}
    with engine.connect() as c:gaps=discovery_gaps(c)
    review_date=max(m['checked_on'] for m in manifests)
    return {'generated_at':datetime.now().astimezone().isoformat(),'review_date':review_date,'summary':summarize(rows),'coverage':coverage,'planning_coverage':planning_summary(engine),'capacity_evidence':capacity_links,'sources':rows,'discovery_gaps':gaps,
        'reviewed_references':[{'source_code':d['source_code'],'title':d['title'],'url':d['url'],'published_at':d['published_at'],'note':d['note']} for d in reference_docs.values()],
        'limitations':['Google News는 발견 도구입니다. 문서 승인이 센터의 모든 필드 확정을 의미하지 않습니다.','기관별 시장 정의·지역·기준일이 달라 공개 보고서의 합계를 센터 합계에 더하지 않습니다.','유료 DB는 상품 소개만 확인했습니다. 원장·가격·임차인 데이터는 취득하지 않았습니다.','공공 API 소스 등록은 연동 완료를 의미하지 않습니다.','운영 IT Load는 운영 시설의 공개 총용량입니다. 실측 부하·점유·가용용량을 의미하지 않습니다.']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'docs/source_audit/latest.json');a=p.parse_args()
    load_env_file();e=create_engine(resolve_database_url())
    try:r=assess(e)
    finally:e.dispose()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=str)+'\n')
    print(json.dumps({'summary':r['summary'],'coverage':r['coverage'],'capacity_evidence':r['capacity_evidence']},ensure_ascii=False,default=str))
    return 0
if __name__=='__main__':raise SystemExit(main())
