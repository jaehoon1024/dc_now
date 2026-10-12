"""Shared manager shell and explicitly allowed, non-secret static assets."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = {
    '/manager.css': ('manager.css', 'text/css; charset=utf-8'),
    '/manager-core.js': ('manager-core.js', 'application/javascript; charset=utf-8'),
    '/manager.js': ('manager.js', 'application/javascript; charset=utf-8'),
}


def page(mode='public'):
    source = (ROOT/'dashboard'/'manager.html').read_text(encoding='utf-8')
    return source.replace('data-mode="public"', 'data-mode="internal"') if mode == 'internal' else source


def static_response(path, start):
    if path not in ASSETS:
        return None
    name, mime = ASSETS[path]
    body = (ROOT/'dashboard'/name).read_bytes()
    start('200 OK', [('Content-Type', mime), ('Content-Length', str(len(body))),
                     ('Cache-Control', 'no-cache'), ('X-Content-Type-Options', 'nosniff')])
    return [body]
