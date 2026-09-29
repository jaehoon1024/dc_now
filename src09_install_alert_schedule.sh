#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="dc-collection-alert.service"
TIMER_NAME="dc-collection-alert.timer"

install_units() {
  mkdir -p "${UNIT_DIR}"
  cat >"${UNIT_DIR}/${SERVICE_NAME}" <<EOF
[Unit]
Description=Check dc-platform collection health
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/.venv/bin/python -B ${PROJECT_DIR}/src09_collection_alert.py
EOF

  cat >"${UNIT_DIR}/${TIMER_NAME}" <<EOF
[Unit]
Description=Daily dc-platform collection health check

[Timer]
OnCalendar=*-*-* 07:15:00 Asia/Seoul
Persistent=true
RandomizedDelaySec=5m
Unit=${SERVICE_NAME}

[Install]
WantedBy=timers.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable --now "${TIMER_NAME}"
  systemctl --user list-timers "${TIMER_NAME}" --all
}

disable_units() {
  systemctl --user disable --now "${TIMER_NAME}" 2>/dev/null || true
  rm -f "${UNIT_DIR}/${SERVICE_NAME}" "${UNIT_DIR}/${TIMER_NAME}"
  systemctl --user daemon-reload
}

case "${1:-}" in
  --enable) install_units ;;
  --disable) disable_units ;;
  *) printf '사용법: %s --enable|--disable\n' "$0" >&2; exit 2 ;;
esac
