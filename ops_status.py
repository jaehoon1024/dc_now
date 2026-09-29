#!/usr/bin/env python3
"""Read-only operating status; explicitly selected fields exclude credentials/logs."""
import argparse
import html
import json
import subprocess
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine, text
from src04_rss_collector import load_env_file, resolve_database_url

ROOT = Path(__file__).resolve().parent
QUERIES = {
    'DB': "SELECT current_setting('server_version') AS postgresql, (SELECT extversion FROM pg_extension WHERE extname='postgis') AS postgis, (SELECT version_num FROM alembic_version LIMIT 1) AS revision",
    '건수': "SELECT (SELECT count(*) FROM source_registry) AS sources, (SELECT count(*) FROM source_registry WHERE active) AS active_sources, (SELECT count(*) FROM source_feed) AS feeds, (SELECT count(*) FROM source_page) AS pages, (SELECT count(*) FROM evidence_document) AS documents, (SELECT count(*) FROM collection_run) AS runs, (SELECT count(*) FROM dc_site) AS sites, (SELECT count(*) FROM dc_project) AS projects",
    '최근 수집': "SELECT DISTINCT ON (job_name) job_name, run_status, started_at, finished_at, new_document_count, updated_document_count FROM collection_run ORDER BY job_name, started_at DESC",
    '수집 이력': "SELECT job_name, run_status, started_at, finished_at, new_document_count, updated_document_count FROM collection_run ORDER BY started_at DESC LIMIT 30",
    '피드': "SELECT sr.source_code, sf.feed_code, sf.active, sf.last_success_at, sf.consecutive_failure_count FROM source_feed sf JOIN source_registry sr USING(source_id) ORDER BY sr.source_code,sf.feed_code",
    '뉴스룸 페이지': "SELECT sr.source_code, sp.page_code, sp.active, sp.last_success_at, sp.consecutive_failure_count FROM source_page sp JOIN source_registry sr USING(source_id) ORDER BY sr.source_code,sp.page_code",
    '출처': "SELECT source_code, collection_method, collection_policy, terms_review_status, active FROM source_registry ORDER BY source_code",
}

def snapshot():
    load_env_file(ROOT / '.env')
    result = {'generated_at': datetime.now().astimezone().isoformat(), 'sections': {}}
    engine = create_engine(resolve_database_url(), connect_args={'options': '-c default_transaction_read_only=on -c statement_timeout=10000'}, echo=False)
    try:
        with engine.connect() as conn:
            for label, query in QUERIES.items():
                result['sections'][label] = [dict(row) for row in conn.execute(text(query)).mappings()]
    finally:
        engine.dispose()
    timers = []
    for name in ['dc-opendart-collector.timer', 'dc-rss-collector.timer', 'dc-newsroom-collector.timer', 'dc-collection-alert.timer', 'dc-weekly-backup.timer', 'dc-quality-report.timer', 'dc-service-health.timer', 'dc-retention-preview.timer']:
        p = subprocess.run(['systemctl', '--user', 'show', name, '-p', 'Id', '-p', 'ActiveState', '-p', 'UnitFileState', '-p', 'NextElapseUSecRealtime', '-p', 'LastTriggerUSec'], capture_output=True, text=True, timeout=10)
        timers.append(dict(line.split('=', 1) for line in p.stdout.splitlines() if '=' in line) if p.returncode == 0 else {'Id': name, 'state': '조회 실패'})
    result['sections']['타이머'] = timers
    tasks = ROOT / 'docs/task_status.json'
    if tasks.exists():result['sections']['개발 작업'] = json.loads(tasks.read_text())
    return result

def render(report):
    esc = lambda value: html.escape('—' if value is None else str(value))
    sections = []
    for title, rows in report['sections'].items():
        keys = list(dict.fromkeys(k for row in rows for k in row))
        head = ''.join('<th>' + esc(k) + '</th>' for k in keys)
        body = ''.join('<tr>' + ''.join('<td>' + esc(row.get(k)) + '</td>' for k in keys) + '</tr>' for row in rows)
        sections.append('<section><h2>' + esc(title) + '</h2><div class="scroll"><table><thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table></div></section>')
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>데이터센터 수집 운영 현황</title><style>
body{font:15px system-ui,sans-serif;margin:0;background:#f1f5f9;color:#14213d}main{max-width:1400px;margin:auto;padding:32px}h1{font-size:30px}h2{font-size:19px}section{background:white;border:1px solid #d9e2ed;border-radius:12px;padding:20px;margin:18px 0}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;white-space:nowrap}td,th{text-align:left;padding:11px;border-bottom:1px solid #e2e8f0}th{background:#eef3fa;font-size:13px}input{padding:12px;width:min(90%,500px);border:1px solid #abb9ce;border-radius:8px}.note{color:#52627a}tr[hidden]{display:none}</style><main><h1>데이터센터 수집 운영 현황</h1><p class="note">생성 시각: ''' + esc(report['generated_at']) + ''' · 저장된 시점의 현황입니다.</p><label>검색 <input id="filter" placeholder="출처·상태·작업 검색"></label>''' + ''.join(sections) + '''<p class="note">갱신: .venv/bin/python -B ops_status.py --html dashboard/status.html</p></main><script>document.querySelector('#filter').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q))});</script></html>'''

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--html', type=Path)
    args = parser.parse_args()
    try:
        report = snapshot()
        if args.html:
            args.html.write_text(render(report), encoding='utf-8')
            print('운영 현황 저장:', args.html.resolve())
        else:print(json.dumps(report, default=str, ensure_ascii=False, indent=2))
        return 0
    except Exception as error:
        print('운영 현황 조회 실패:', type(error).__name__)
        return 1

if __name__ == '__main__':raise SystemExit(main())
