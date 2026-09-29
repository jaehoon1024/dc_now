#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; UNITS="${HOME}/.config/systemd/user"
install_all(){
 mkdir -p "$UNITS"
 cat >"$UNITS/dc-internal-api.service" <<EOF
[Unit]
Description=dc-platform authenticated internal API
After=network-online.target
[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$ROOT/.venv/bin/python -B $ROOT/internal_api.py --host 127.0.0.1 --port 8766
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=default.target
EOF
 make_timer dc-weekly-backup "Weekly verified database backup" "Sun *-*-* 03:20:00 Asia/Seoul" "$ROOT/.venv/bin/python -B $ROOT/src17_backup.py create"
 make_timer dc-quality-report "Daily quality report" "*-*-* 07:30:00 Asia/Seoul" "$ROOT/.venv/bin/python -B $ROOT/src15_quality_report.py --json $ROOT/dashboard/quality.json --html $ROOT/dashboard/quality.html"
 make_timer dc-service-health "Hourly service health report" "hourly" "$ROOT/.venv/bin/python -B $ROOT/src18_service_health.py --json $ROOT/dashboard/health.json"
 make_timer dc-retention-preview "Weekly retention preview" "Mon *-*-* 08:00:00 Asia/Seoul" "$ROOT/.venv/bin/python -B $ROOT/src19_retention.py exports --manifest $ROOT/dashboard/retention_preview.json"
 systemctl --user daemon-reload
 systemctl --user enable --now dc-internal-api.service dc-weekly-backup.timer dc-quality-report.timer dc-service-health.timer dc-retention-preview.timer
}
make_timer(){ local name="$1" desc="$2" calendar="$3" command="$4";cat >"$UNITS/$name.service" <<EOF
[Unit]
Description=$desc
[Service]
Type=oneshot
WorkingDirectory=$ROOT
ExecStart=$command
EOF
 cat >"$UNITS/$name.timer" <<EOF
[Unit]
Description=$desc schedule
[Timer]
OnCalendar=$calendar
Persistent=true
RandomizedDelaySec=5m
Unit=$name.service
[Install]
WantedBy=timers.target
EOF
}
disable_all(){ systemctl --user disable --now dc-internal-api.service dc-weekly-backup.timer dc-quality-report.timer dc-service-health.timer dc-retention-preview.timer 2>/dev/null||true; }
case "${1:-}" in --enable) install_all;;--disable) disable_all;;*) echo "사용법: $0 --enable|--disable" >&2;exit 2;;esac
