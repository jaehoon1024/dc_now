#!/usr/bin/env python3
"""Check database, API, timers, disk, and latest collection runs."""
from __future__ import annotations
import argparse,json,shutil,subprocess
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen
from sqlalchemy import create_engine,text
from src04_rss_collector import load_env_file,resolve_database_url
ROOT=Path(__file__).resolve().parent
TIMERS=("dc-opendart-collector.timer","dc-rss-collector.timer","dc-newsroom-collector.timer","dc-collection-alert.timer")
def check(engine):
 out={"checked_at":datetime.now(timezone.utc).isoformat(),"database":False,"api":False,"timers":{},"disk":{},"collections":[]}
 try:
  with engine.connect() as c:
   c.execute(text("SELECT 1"));out["database"]=True;out["collections"]=[dict(r) for r in c.execute(text("SELECT DISTINCT ON(job_name) job_name,run_status,finished_at FROM collection_run ORDER BY job_name,started_at DESC")).mappings()]
 except Exception:pass
 try:
  with urlopen("http://127.0.0.1:8765/api/v1/healthz",timeout=3) as r:out["api"]=r.status==200
 except Exception:pass
 for timer in TIMERS:
  p=subprocess.run(["systemctl","--user","is-active",timer],capture_output=True,text=True,timeout=3);out["timers"][timer]=p.stdout.strip()=="active"
 d=shutil.disk_usage(ROOT);out["disk"]={"free_bytes":d.free,"used_percent":round(d.used/d.total*100,1),"healthy":d.free>2*1024**3}
 out["healthy"]=out["database"] and out["api"] and all(out["timers"].values()) and out["disk"]["healthy"] and all(x["run_status"]=="SUCCESS" for x in out["collections"])
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument("--json",type=Path);a=p.parse_args();load_env_file();e=create_engine(resolve_database_url(),connect_args={"options":"-c default_transaction_read_only=on"})
 try:r=check(e)
 finally:e.dispose()
 data=json.dumps(r,default=str,ensure_ascii=False,indent=2)
 if a.json:a.json.write_text(data,encoding="utf-8")
 else:print(data)
 return 0 if r["healthy"] else 2
if __name__=="__main__":raise SystemExit(main())
