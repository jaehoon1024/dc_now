"""Shared manager shell and explicitly allowed, non-secret static assets."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = {
    '/manager.css': ('manager.css', 'text/css; charset=utf-8'),
    '/manager-core.js': ('manager-core.js', 'application/javascript; charset=utf-8'),
    '/manager.js': ('manager.js', 'application/javascript; charset=utf-8'),
    '/market.css': ('market.css', 'text/css; charset=utf-8'),
    '/market.js': ('market.js', 'application/javascript; charset=utf-8'),
    '/development.js': ('development.js', 'application/javascript; charset=utf-8'),
    '/google-map.js': ('google-map.js', 'application/javascript; charset=utf-8'),
    '/map-config.json': ('map-config.json', 'application/json; charset=utf-8'),
}


def page(mode='public'):
    source = (ROOT/'dashboard'/'manager.html').read_text(encoding='utf-8')
    return source.replace('data-mode="public"', 'data-mode="internal"').replace('href="./">시장 대시보드', 'href="https://jaehoon1024.github.io/dc_now/">시장 대시보드') if mode == 'internal' else source


def market_page():
    return (ROOT/'dashboard'/'market.html').read_text(encoding='utf-8')

def static_response(path, start):
    if path not in ASSETS:
        return None
    name, mime = ASSETS[path]
    body = (ROOT/'dashboard'/name).read_bytes()
    start('200 OK', [('Content-Type', mime), ('Content-Length', str(len(body))),
                     ('Cache-Control', 'no-cache'), ('X-Content-Type-Options', 'nosniff')])
    return [body]
