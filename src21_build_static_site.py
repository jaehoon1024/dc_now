#!/usr/bin/env python3
"""Build a Netlify-ready snapshot containing approved public data only."""
from __future__ import annotations
import json,shutil
from datetime import datetime
from pathlib import Path
from sqlalchemy import create_engine
from public_api import PublicRepository,json_value
from src04_rss_collector import load_env_file,resolve_database_url
ROOT=Path(__file__).resolve().parent;OUT=ROOT/"deploy"
def build_payload(repo):
 sites,total=repo.sites(None,None,500,0)
 details={x["site_code"]:repo.site_detail(x["site_code"]) for x in sites}
 return {"generated_at":datetime.now().astimezone().isoformat(),"total":total,"sites":sites,"details":details,"regions":repo.regions(),"companies":repo.companies(),"yearly":repo.yearly(),"collection_status":repo.collection_status()}
def write_site(payload,out=OUT):
 out.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/"dashboard/static.html",out/"index.html")
 (out/"data.json").write_text(json.dumps(payload,ensure_ascii=False,default=json_value,separators=(",",":")),encoding="utf-8")
 (out/"_headers").write_text("/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n  Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'\n\n/data.json\n  Cache-Control: public, max-age=300\n",encoding="utf-8")
def main():
 load_env_file();e=create_engine(resolve_database_url(),connect_args={"options":"-c default_transaction_read_only=on -c statement_timeout=10000"})
 try:payload=build_payload(PublicRepository(e))
 finally:e.dispose()
 write_site(payload);print(f"정적 사이트 생성: {OUT} / 공개 센터 {payload['total']}건");return 0
if __name__=="__main__":raise SystemExit(main())
