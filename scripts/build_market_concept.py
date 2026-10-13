#!/usr/bin/env python3
"""Build a standalone screen concept from the existing public snapshot, without DB writes."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]

def build():
    snapshot = json.loads((ROOT / 'deploy/data.json').read_text(encoding='utf-8'))
    page = (ROOT / 'dashboard/market.html').read_text(encoding='utf-8')
    page = page.replace('<link rel="stylesheet" href="./market.css">', '<style>' + (ROOT / 'dashboard/market.css').read_text(encoding='utf-8') + '</style>')
    for name in ('manager-core.js', 'google-map.js', 'development.js', 'market.js'):
        code = (ROOT / 'dashboard' / name).read_text(encoding='utf-8').replace('</script', '<\\/script')
        page = page.replace(f'<script src="./{name}"></script>', f'<script>{code}</script>')
    payload = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    page = page.replace('./manage.html','https://jaehoon1024.github.io/dc_now/manage.html')
    page = page.replace('<!--MARKET_DATA-->', f'<script id="conceptSnapshot" type="application/json">{payload}</script>')
    target = ROOT / 'output/design/dc-market-concept.html'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding='utf-8')
    print(f'Created {target}; {len(snapshot["sites"])} tracked centers; snapshot {snapshot["generated_at"]}')
    return target

if __name__ == '__main__':
    build()
