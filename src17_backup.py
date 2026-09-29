#!/usr/bin/env python3
"""Create, verify, and retain PostgreSQL custom-format backups."""
from __future__ import annotations
import argparse,hashlib,json,os,subprocess,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from sqlalchemy.engine import make_url
from src04_rss_collector import load_env_file,resolve_database_url
ROOT=Path(__file__).resolve().parent;BACKUPS=ROOT/"data/backups"
def sha256(path):
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def safe_backups(root=BACKUPS):return [p for p in root.glob("dc_platform_*.dump") if p.is_file() and p.parent.resolve()==root.resolve()]
def create_backup(root=BACKUPS):
 root.mkdir(parents=True,exist_ok=True);stamp=datetime.now().astimezone().strftime("%Y%m%d_%H%M%S");out=root/f"dc_platform_{stamp}.dump";tmp=out.with_suffix(".tmp")
 env=os.environ.copy();env["PGPASSWORD"]=os.environ["DC_DB_PASSWORD"]
 url=make_url(resolve_database_url())
 command=["pg_dump","--format=custom","--no-owner","--no-acl","--file",str(tmp),"--host",str(url.host),"--port",str(url.port or 5432),"--username",str(url.username),"--dbname",str(url.database)]
 try:subprocess.run(command,check=True,env=env,capture_output=True)
 except subprocess.CalledProcessError:tmp.unlink(missing_ok=True);raise RuntimeError("pg_dump failed") from None
 tmp.replace(out)
 try:subprocess.run(["pg_restore","--list",str(out)],check=True,capture_output=True)
 except subprocess.CalledProcessError:raise RuntimeError("pg_restore verification failed") from None
 manifest={"file":out.name,"created_at":datetime.now(timezone.utc).isoformat(),"bytes":out.stat().st_size,"sha256":sha256(out),"verified":True}
 out.with_suffix(".json").write_text(json.dumps(manifest,indent=2),encoding="utf-8");return out,manifest
def retention_candidates(days,root=BACKUPS,now=None):
 cutoff=(now or datetime.now(timezone.utc))-timedelta(days=days);return [p for p in safe_backups(root) if datetime.fromtimestamp(p.stat().st_mtime,timezone.utc)<cutoff]
def main():
 p=argparse.ArgumentParser();p.add_argument("command",choices=("create","verify","retention"));p.add_argument("path",nargs="?",type=Path);p.add_argument("--days",type=int,default=30);p.add_argument("--apply",action="store_true");a=p.parse_args();load_env_file()
 if a.command=="create":out,m=create_backup();print(json.dumps(m));return 0
 if a.command=="verify":
  if not a.path or a.path.parent.resolve()!=BACKUPS.resolve():print("허용된 백업 경로가 아닙니다.",file=sys.stderr);return 2
  subprocess.run(["pg_restore","--list",str(a.path)],check=True,capture_output=True);print(sha256(a.path));return 0
 old=retention_candidates(a.days)
 for f in old:
  print(f.name)
  if a.apply:f.unlink();f.with_suffix(".json").unlink(missing_ok=True)
 print(f"대상 {len(old)}건 / {'삭제' if a.apply else 'dry-run'}");return 0
if __name__=="__main__":raise SystemExit(main())
