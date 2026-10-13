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

def group(row):
    if row['source_code'].endswith('_LICENSED'):return '유료 전문 데이터'
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
    with engine.connect() as c:
        rows=[dict(r) for r in c.execute(text('''SELECT sr.source_code,sr.source_name,sr.source_type,sr.base_url,sr.collection_method,sr.collection_policy,sr.active,
            COUNT(ed.document_id)::int AS documents,
            COUNT(ed.document_id) FILTER(WHERE ed.review_status='CONFIRMED' AND ed.access_scope='PUBLIC')::int AS public_confirmed,
            COUNT(ed.document_id) FILTER(WHERE ed.canonical_url LIKE 'https://news.google.com/%')::int AS aggregator_urls,
            MAX(ed.created_at) AS latest_imported_at
            FROM source_registry sr LEFT JOIN evidence_document ed ON ed.source_id=sr.source_id AND ed.record_status='ACTIVE'
            GROUP BY sr.source_id ORDER BY COUNT(ed.document_id) DESC,sr.source_code''')).mappings()]
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
    manifest=json.loads((ROOT/'data/reference/source_review_2026-10-13.json').read_text())
    return {'generated_at':datetime.now().astimezone().isoformat(),'review_date':manifest['checked_on'],'summary':summarize(rows),'coverage':coverage,'capacity_evidence':capacity_links,'sources':rows,
        'reviewed_references':[{'source_code':d['source_code'],'title':d['title'],'url':d['url'],'published_at':d['published_at'],'note':d['note']} for d in manifest['documents']],
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
