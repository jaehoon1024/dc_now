#!/usr/bin/env python3
"""Final release-readiness checks without exposing configuration secrets."""
from __future__ import annotations
import json,subprocess
from pathlib import Path
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parent
REQUIRED=("public_api.py","internal_api.py","src17_backup.py","src18_service_health.py","src19_retention.py","dashboard/public.html","dashboard/admin.html","docs/disaster_recovery.md","docs/security.md","docs/api.md")
SERVICES=("dc-public-api.service","dc-internal-api.service")
TIMERS=("dc-opendart-collector.timer","dc-rss-collector.timer","dc-newsroom-collector.timer","dc-collection-alert.timer","dc-weekly-backup.timer","dc-quality-report.timer","dc-service-health.timer","dc-retention-preview.timer")
def evaluate(files,services,timers,public_api,backup):return {"files":all(files),"services":all(services),"timers":all(timers),"public_api":public_api,"backup":backup,"ready":all(files) and all(services) and all(timers) and public_api and backup}
def main():
 files=[(ROOT/x).exists() for x in REQUIRED]
 active=lambda x:subprocess.run(["systemctl","--user","is-active","--quiet",x]).returncode==0
 services=[active(x) for x in SERVICES];timers=[active(x) for x in TIMERS]
 try:
  with urlopen("http://127.0.0.1:8765/api/v1/healthz",timeout=3) as r:api=r.status==200
 except Exception:api=False
 manifests=sorted((ROOT/"data/backups").glob("dc_platform_*.json"));backup=False
 if manifests:
  try:backup=bool(json.loads(manifests[-1].read_text()).get("verified"))
  except Exception:pass
 result=evaluate(files,services,timers,api,backup);print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result["ready"] else 2
if __name__=="__main__":raise SystemExit(main())
