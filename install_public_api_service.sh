#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
UNIT_NAME="dc-public-api.service"

enable_service() {
  mkdir -p "${UNIT_DIR}"
  cat >"${UNIT_DIR}/${UNIT_NAME}" <<EOF
[Unit]
Description=dc-platform read-only public API
After=network-online.target postgresql.service

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/.venv/bin/python -B ${PROJECT_DIR}/public_api.py --host 127.0.0.1 --port 8765
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now "${UNIT_NAME}"
  systemctl --user status "${UNIT_NAME}" --no-pager
}

disable_service() {
  systemctl --user disable --now "${UNIT_NAME}" 2>/dev/null || true
  rm -f "${UNIT_DIR}/${UNIT_NAME}"
  systemctl --user daemon-reload
}

case "${1:-}" in
  --enable) enable_service ;;
  --disable) disable_service ;;
  *) printf '사용법: %s --enable|--disable\n' "$0" >&2; exit 2 ;;
esac
