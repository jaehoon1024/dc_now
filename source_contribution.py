"""Public, secret-free source diagnostics with document and fact counts kept separate."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent

def official_state():
    file=ROOT/'data/reference/official_collection_latest.json'
    if not file.exists():return {}
    return {r['source_code']:r for r in json.loads(file.read_text()).get('sources',[])}


def diagnose(row,official=None):
    official=official or {}
    code=row['source_code'];routes=int(row.get('configured_routes') or 0)
    if code.endswith('_LICENSED'):
        return 'CONTRACT_REQUIRED','계약 필요 · 미취득','계약 후 허용 범위로 연동'
    if not row.get('active',True) or row.get('collection_policy')=='BLOCKED':
        return 'INACTIVE','직접 수집 비활성','수집 정책과 연결 경로 검토'
    if official.get('status')=='FAILED':
        actions={'TLS_CERTIFICATE_ERROR':'공식 사이트 인증서 체인 확인','REDIRECT_REVIEW_REQUIRED':'공식 주소 전환 확인','ROBOTS_REVIEW_REQUIRED':'수집 규칙 파일 확인','ROBOTS_DISALLOWED':'직접 수집 제한 · 다른 공개 근거 검토','NO_RELEVANT_CONTENT':'시설 안내 주소·페이지 형식 확인','CONNECTION_ERROR':'네트워크 연결 확인'}
        return 'FAILED','공식 페이지 확인 실패',actions.get(official.get('error_code'),'공식 사이트 연결·응답 확인')
    if row.get('failing_routes',0):
        return 'FAILED','실패한 수집 경로 있음','연결 주소·파서 점검'
    if routes:
        if not row.get('latest_success_at') and official.get('status')!='SUCCESS':
            return 'NOT_RUN','수집 경로 준비 · 성공 이력 없음','첫 실행 결과 확인'
        return 'CONNECTED','직접 수집 연결','신규·확정·정보 확보 항목 확인'
    if row.get('collection_method')=='API':
        return 'API_NOT_CONNECTED','API 수집기 미연결','공식 API 연결·이용권한 확인'
    if row.get('documents',0):
        return 'MANUAL','수동 취득','공식 페이지·보고서 주기 확인'
    return 'NOT_CONNECTED','등록만 · 취득 경로 없음','자료 취득 경로 연결'


def enrich_rows(rows,connection,official=None):
    from sqlalchemy import text
    official=official_state() if official is None else official
    route_rows=connection.execute(text("""SELECT sr.source_code,count(*) FILTER(WHERE r.active)::int AS configured_routes,
        max(r.last_polled_at) AS latest_attempt_at,max(r.last_success_at) AS latest_success_at,
        count(*) FILTER(WHERE r.active AND r.consecutive_failure_count>0)::int AS failing_routes
      FROM source_registry sr JOIN (
        SELECT source_id,active,last_polled_at,last_success_at,consecutive_failure_count FROM source_feed
        UNION ALL SELECT source_id,active,last_polled_at,last_success_at,consecutive_failure_count FROM source_page
      ) r USING(source_id) GROUP BY sr.source_code""")).mappings()
    routes={r['source_code']:dict(r) for r in route_rows}
    facts=connection.execute(text("""SELECT sr.source_code,count(DISTINCT f.fact_id)::int AS confirmed_facts
      FROM source_registry sr JOIN evidence_document ed USING(source_id)
      JOIN evidence_document_version ev USING(document_id) JOIN fact_evidence fe USING(document_version_id)
      JOIN extracted_fact f USING(fact_id)
      WHERE ed.access_scope='PUBLIC' AND ed.review_status='CONFIRMED' AND ed.record_status='ACTIVE'
        AND f.review_status='CONFIRMED' GROUP BY sr.source_code""")).mappings()
    fact_counts={r['source_code']:r['confirmed_facts'] for r in facts}
    caps=connection.execute(text("""SELECT sr.source_code,count(DISTINCT cs.capacity_id)::int AS confirmed_capacities
      FROM source_registry sr JOIN evidence_document ed USING(source_id)
      JOIN capacity_snapshot cs ON cs.document_url=ed.canonical_url
      WHERE ed.access_scope='PUBLIC' AND ed.review_status='CONFIRMED' AND ed.record_status='ACTIVE'
        AND cs.review_status='CONFIRMED' GROUP BY sr.source_code""")).mappings()
    cap_counts={r['source_code']:r['confirmed_capacities'] for r in caps}
    catalog=ROOT/'data/reference/official_collection_catalog.json'
    configured={x['source_code'] for x in json.loads(catalog.read_text())['sources']} if catalog.exists() else set()
    notes_path=ROOT/'data/reference/source_collection_notes.json'
    notes=json.loads(notes_path.read_text()).get('sources',{}) if notes_path.exists() else {}
    coverage_path=ROOT/'data/reference/newsroom_coverage_latest.json'
    coverage={r['source_code']:r for r in json.loads(coverage_path.read_text()).get('sources',[])} if coverage_path.exists() else {}
    dart_run=connection.execute(text("SELECT started_at,finished_at,run_status FROM collection_run WHERE job_name='OPENDART_DAILY' ORDER BY started_at DESC LIMIT 1")).mappings().first()
    for row in rows:
        code=row['source_code'];state=official.get(code,{})
        row['scope_note']=notes.get(code,{}).get('scope_note') or ('공식 시설 안내 URL의 제목·링크를 확인합니다. 시설의 개별 수치는 별도 검토합니다.' if code in configured else '')
        row['collection_coverage']=coverage.get(code)

        row.update(routes.get(code,{'configured_routes':0,'failing_routes':0,'latest_attempt_at':None,'latest_success_at':None}))
        row['configured_routes']+=int(code in configured)+int(code=='OPENDART')
        row['confirmed_facts']=fact_counts.get(code,0);row['confirmed_capacities']=cap_counts.get(code,0)
        row['permit_records']=0
        if state:
            row['official_collection']={k:state.get(k) for k in ['status','attempted_at','last_success_at','new_documents','error_code','robots_status']}
            row['latest_attempt_at']=state.get('attempted_at');row['latest_success_at']=state.get('last_success_at')
        if code=='OPENDART' and dart_run:
            row['latest_attempt_at']=dart_run['started_at']
            if dart_run['run_status']=='SUCCESS':row['latest_success_at']=dart_run['finished_at']
            elif dart_run['run_status'] in {'FAILED','PARTIAL'}:row['failing_routes']=1
        status,label,action=diagnose(row,state)
        row.update(connection_status=status,connection_label=label,required_action=action)
    return rows
