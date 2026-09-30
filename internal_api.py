#!/usr/bin/env python3
"""Token-authenticated local API for review and quality operations."""
from __future__ import annotations
import argparse,hmac,json,os
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from sqlalchemy import create_engine
from src04_rss_collector import load_env_file,resolve_database_url
from src14_review_workflow import ENTITIES,queue,review
from src15_quality_report import build_report
from pathlib import Path
ADMIN_HTML=Path(__file__).resolve().parent/"dashboard/admin.html"
def response(start,status,payload):
 b=json.dumps(payload,default=str,ensure_ascii=False).encode();start(status,[("Content-Type","application/json; charset=utf-8"),("Content-Length",str(len(b))),("Cache-Control","no-store"),("X-Content-Type-Options","nosniff")]);return[b]
def make_app(engine,token):
 def app(env,start):
  auth=env.get("HTTP_AUTHORIZATION","")
  if env.get("REQUEST_METHOD")=="GET" and env.get("PATH_INFO")=="/":
   b=ADMIN_HTML.read_bytes();start("200 OK",[("Content-Type","text/html; charset=utf-8"),("Content-Length",str(len(b))),("Cache-Control","no-store"),("Content-Security-Policy","default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")]);return[b]
  if not hmac.compare_digest(auth,f"Bearer {token}"):return response(start,"401 Unauthorized",{"error":"unauthorized"})
  path=env.get("PATH_INFO","");method=env.get("REQUEST_METHOD")
  try:
   if method=="GET" and path=="/internal/v1/review-queue":return response(start,"200 OK",queue(engine,limit=500))
   if method=="GET" and path=="/internal/v1/quality":return response(start,"200 OK",build_report(engine))
   if method=="POST" and path=="/internal/v1/review":
    size=min(int(env.get("CONTENT_LENGTH") or 0),10000);data=json.loads(env["wsgi.input"].read(size));required={"kind","record_id","decision","reviewer","note"}
    if (not required<=data.keys() or data["kind"] not in ENTITIES
        or data["decision"] not in {"approve","reject"}
        or not str(data["reviewer"]).strip() or not str(data["note"]).strip()):
     return response(start,"400 Bad Request",{"error":"invalid_request"})
    return response(start,"200 OK",review(engine,data["kind"],data["record_id"],data["decision"],data["reviewer"],data["note"],bool(data.get("publish"))))
   return response(start,"404 Not Found",{"error":"not_found"})
  except (ValueError,KeyError,json.JSONDecodeError):return response(start,"400 Bad Request",{"error":"invalid_request"})
  except Exception:return response(start,"503 Service Unavailable",{"error":"service_unavailable"})
 return app
def main():
 p=argparse.ArgumentParser();p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8766);a=p.parse_args();load_env_file();token=os.getenv("ADMIN_API_TOKEN","")
 if len(token)<32:raise SystemExit("ADMIN_API_TOKEN은 32자 이상이어야 합니다.")
 e=create_engine(resolve_database_url(),pool_pre_ping=True)
 try:
  with make_server(a.host,a.port,make_app(e,token)) as s:s.serve_forever()
 finally:e.dispose()
if __name__=="__main__":main()
