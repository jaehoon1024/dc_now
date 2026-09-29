#!/usr/bin/env bash
set -Eeuo pipefail

# SRC-04: RSS 수집기를 systemd 사용자 타이머로 설치합니다.
# 기본 실행은 설치만 수행하고, --enable을 지정해야 활성화됩니다.

readonly SERVICE_NAME="dc-rss-collector.service"
readonly TIMER_NAME="dc-rss-collector.timer"
readonly PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly COLLECTOR_PATH="${PROJECT_DIR}/src04_rss_collector.py"
readonly ENV_PATH="${PROJECT_DIR}/.env"
readonly UNIT_DIR="${HOME}/.config/systemd/user"
readonly SERVICE_PATH="${UNIT_DIR}/${SERVICE_NAME}"
readonly TIMER_PATH="${UNIT_DIR}/${TIMER_NAME}"

ACTION="install"
if [[ "${1:-}" == "--enable" ]]; then
  ACTION="enable"
elif [[ "${1:-}" == "--disable" ]]; then
  ACTION="disable"
elif [[ -n "${1:-}" ]]; then
  echo "사용법: bash $0 [--enable|--disable]" >&2
  exit 2
fi

if [[ "${ACTION}" == "disable" ]]; then
  systemctl --user disable --now "${TIMER_NAME}" 2>/dev/null || true
  echo "RSS 자동수집 타이머를 중지했습니다."
  exit 0
fi

if [[ ! -f "${COLLECTOR_PATH}" ]]; then
  echo "수집기 파일이 없습니다: ${COLLECTOR_PATH}" >&2
  exit 1
fi

if ! command -v systemctl >/dev/null 2>&1; then
  echo "systemctl을 찾을 수 없습니다. WSL systemd 설정이 필요합니다." >&2
  exit 1
fi

if [[ "$(ps -p 1 -o comm= 2>/dev/null | tr -d ' ')" != "systemd" ]]; then
  cat >&2 <<'MESSAGE'
WSL에서 systemd가 실행 중이 아닙니다.
다음 내용을 /etc/wsl.conf에 추가한 뒤 PowerShell에서 wsl --shutdown을 실행하세요.

[boot]
systemd=true
MESSAGE
  exit 1
fi

if ! systemctl --user show-environment >/dev/null 2>&1; then
  cat >&2 <<'MESSAGE'
사용자 systemd 세션에 연결하지 못했습니다.
Ubuntu를 다시 시작한 뒤 로그인한 사용자 계정에서 다시 실행하세요.
MESSAGE
  exit 1
fi

mkdir -p "${UNIT_DIR}"

cat >"${SERVICE_PATH}" <<UNIT
[Unit]
Description=DC Platform RSS metadata collection
Documentation=https://www.rssboard.org/rss-specification

[Service]
Type=oneshot
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${ENV_PATH}
ExecStart=${PROJECT_DIR}/.venv/bin/python ${COLLECTOR_PATH} --trigger SCHEDULED
UMask=0077
Nice=10
TimeoutStartSec=30min
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
UNIT

cat >"${TIMER_PATH}" <<UNIT
[Unit]
Description=Run DC Platform RSS collection every morning

[Timer]
OnCalendar=*-*-* 06:30:00 Asia/Seoul
Persistent=true
RandomizedDelaySec=5min
AccuracySec=1min
Unit=${SERVICE_NAME}

[Install]
WantedBy=timers.target
UNIT

chmod 600 "${SERVICE_PATH}" "${TIMER_PATH}"
systemctl --user daemon-reload

if [[ "${ACTION}" == "install" ]]; then
  echo "스케줄 파일 설치 완료: 매일 06:30 Asia/Seoul"
  echo "현재 상태: 비활성"
  echo "수집 성공 확인 후 다음 명령으로 활성화하세요:"
  echo "  bash ${PROJECT_DIR}/src04_install_rss_schedule.sh --enable"
  exit 0
fi

if [[ ! -f "${ENV_PATH}" ]]; then
  echo ".env 파일이 없습니다: ${ENV_PATH}" >&2
  exit 1
fi

if ! grep -Eq '^(DATABASE_URL|DC_DB_PASSWORD)=.+' "${ENV_PATH}"; then
  cat >&2 <<'MESSAGE'
자동 실행에는 DB 접속정보가 .env에 있어야 합니다.
DATABASE_URL 또는 DC_DB_PASSWORD를 .env에 등록한 뒤 다시 실행하세요.
MESSAGE
  exit 1
fi

chmod 600 "${ENV_PATH}"
systemctl --user enable --now "${TIMER_NAME}"

echo "RSS 자동수집 타이머를 활성화했습니다."
systemctl --user list-timers "${TIMER_NAME}" --no-pager
