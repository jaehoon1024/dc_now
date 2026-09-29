#!/usr/bin/env bash
set -Eeuo pipefail

readonly SERVICE_NAME="dc-newsroom-collector.service"
readonly TIMER_NAME="dc-newsroom-collector.timer"
readonly PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly UNIT_DIR="${HOME}/.config/systemd/user"
readonly ENV_PATH="${PROJECT_DIR}/.env"

action="${1:---install}"
if [[ "${action}" != "--install" && "${action}" != "--enable" && "${action}" != "--disable" ]]; then
  echo "사용법: bash $0 [--install|--enable|--disable]" >&2
  exit 2
fi

if [[ "${action}" == "--disable" ]]; then
  systemctl --user disable --now "${TIMER_NAME}" 2>/dev/null || true
  echo "기업 뉴스룸 자동수집 타이머를 중지했습니다."
  exit 0
fi

if [[ ! -x "${PROJECT_DIR}/.venv/bin/python" || ! -f "${PROJECT_DIR}/src05_newsroom_collector.py" ]]; then
  echo "뉴스룸 수집기 또는 Python 가상환경을 찾지 못했습니다." >&2
  exit 1
fi
if [[ ! -f "${ENV_PATH}" ]] || ! grep -Eq '^(DATABASE_URL|DC_DB_PASSWORD)=.+' "${ENV_PATH}"; then
  echo "자동 실행에 필요한 DB 접속 설정을 찾지 못했습니다." >&2
  exit 1
fi

mkdir -p "${UNIT_DIR}"
umask 077
tee "${UNIT_DIR}/${SERVICE_NAME}" >/dev/null <<UNIT
[Unit]
Description=DC Platform official newsroom metadata collection
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_PATH}
ExecStart=${PROJECT_DIR}/.venv/bin/python ${PROJECT_DIR}/src05_newsroom_collector.py --trigger SCHEDULED
UMask=0077
Nice=10
TimeoutStartSec=30min
NoNewPrivileges=true
PrivateTmp=true
UNIT

tee "${UNIT_DIR}/${TIMER_NAME}" >/dev/null <<UNIT
[Unit]
Description=Run DC Platform official newsroom collection every morning

[Timer]
OnCalendar=*-*-* 06:50:00 Asia/Seoul
Persistent=true
RandomizedDelaySec=5min
AccuracySec=1min
Unit=${SERVICE_NAME}

[Install]
WantedBy=timers.target
UNIT

systemctl --user daemon-reload
if [[ "${action}" == "--enable" ]]; then
  systemctl --user enable --now "${TIMER_NAME}"
  echo "기업 뉴스룸 자동수집 타이머를 활성화했습니다."
else
  echo "기업 뉴스룸 자동수집 타이머 설치 완료: 매일 06:50 Asia/Seoul"
fi
