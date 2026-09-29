#!/usr/bin/env python3
"""Preview or apply file retention inside approved data directories."""
from __future__ import annotations
import argparse,json
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parent
POLICIES={"exports":(ROOT/"data/exports",30),"raw":(ROOT/"data/raw",180),"backups":(ROOT/"data/backups",30)}
def candidates(kind,days=None,now=None):
 root,default=POLICIES[kind];cut=(now or datetime.now(timezone.utc))-timedelta(days=days or default);out=[]
 if not root.exists():return out
 for p in root.rglob("*"):
  if p.is_file() and p.resolve().is_relative_to(root.resolve()) and datetime.fromtimestamp(p.stat().st_mtime,timezone.utc)<cut:out.append(p)
 return sorted(out)
def run(kind,days=None,apply=False):
 root,_=POLICIES[kind];files=candidates(kind,days);manifest={"kind":kind,"mode":"apply" if apply else "dry-run","count":len(files),"files":[str(p.relative_to(root)) for p in files]}
 if apply:
  for p in files:p.unlink()
 return manifest
def main():
 p=argparse.ArgumentParser();p.add_argument("kind",choices=POLICIES);p.add_argument("--days",type=int);p.add_argument("--apply",action="store_true");p.add_argument("--manifest",type=Path);a=p.parse_args()
 if a.days is not None and a.days<1:raise SystemExit("--days는 1 이상이어야 합니다.")
 r=run(a.kind,a.days,a.apply);data=json.dumps(r,ensure_ascii=False,indent=2);print(data)
 if a.manifest:a.manifest.parent.mkdir(parents=True,exist_ok=True);a.manifest.write_text(data,encoding="utf-8")
 return 0
if __name__=="__main__":raise SystemExit(main())
