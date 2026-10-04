# N100 운영 및 개발 기록

## 2026-10-04 Google News 1년 과거자료 백필

- 상용 데이터센터 관련 검색 결과가 최신 기사에 치우치지 않도록 기간 백필 수집기를 추가했다.
- 대상은 코로케이션·임대·마스터리스, 인허가·착공·준공·부지, 임차·매각·투자, 상용 운영사, 개발사·AMC·시공사·DBO의 5개 검색식이다.
- Google News RSS의 검색 결과 상한을 줄이기 위해 지정 기간을 기본 31일 구간으로 나눠 조회한다.
- RSS에 포함된 게시일을 다시 검사하며 기간 밖 결과와 게시일 없는 결과는 제외한다.
- 기사 본문은 수집하지 않고 제목·URL·발행사·게시일만 저장한다. 신규 문서는 `CANDIDATE` 상태로 검토 대기에 둔다.
- 2025-10-04부터 2026-10-04까지 최초 실행에서 60개 구간, 4,240건을 확인했고 신규 3,279건을 적재했다. 수집 실행 상태는 `SUCCESS`였다.

```bash
.venv/bin/python -u src25_google_news_backfill.py \
  --from-date 2025-10-04 --to-date 2026-10-04 \
  --window-days 31 --max-items 100
```

특정 검색식만 더 짧은 구간으로 보완할 때는 `--feed-code`를 반복 지정한다.

```bash
.venv/bin/python -u src25_google_news_backfill.py \
  --days 365 --window-days 15 \
  --feed-code GNEWS_DC_DEVELOPMENT
```

## 2026-09-28 변경

- RSS의 게시일 없는 응답/304 처리 시 발생한 PostgreSQL AmbiguousParameter 수정: NULL 검사에 timestamptz 명시.
- 잘못된 반복문의 feed_index 참조를 수정. 실패한 피드 뒤에도 요청 간격 유지.
- 실제 6개 피드 실행 성공 확인. 기존 실패 이력은 보존.
- OpenDART 일일 06:10 KST, RSS 일일 00:30·06:30·12:30·18:30 KST 사용자 타이머 활성화. 각각 최대 5분 무작위 지연.
- 사용자 linger 활성화. Windows/WSL 자체가 종료되어 있으면 실행되지 않으며 Persistent 설정으로 다음 시작 시 누락 실행을 보완.
- ops_status.py: 읽기 전용 DB 조회, 타이머 상태, 로컬 Task 목록, 검색 가능한 운영 현황 HTML.
- 비밀번호, API 키, 환경파일 내용은 보고서에 포함하지 않음.

## 운영 현황 갱신

```bash
cd /home/jh1024/dc-platform
.venv/bin/python -B ops_status.py --html dashboard/status.html
```

생성한 HTML은 스냅샷이다. 실시간 서비스나 공개 배포 화면은 아니다.

## 테스트

```bash
DC_TEST_DATABASE=1 .venv/bin/python -B -m unittest discover -s tests -v
```

DB 테스트는 임시 테이블만 사용하고 전체 트랜잭션을 롤백한다. 4개 테스트 통과.

## 일정 관리

```bash
bash src04_install_opendart_schedule.sh --enable
bash src04_install_rss_schedule.sh --enable
systemctl --user list-timers 'dc-*' --all
```

중지는 각 설치 스크립트의 --disable 옵션을 사용한다.

## 후속 개발 기준

[사용자 제공 공유 대화](https://chatgpt.com/share/6aba5fa4-ab6c-83ee-a06b-87eb889b91d8)

최근 명시 단계는 RSS 이후 기업 뉴스룸 검토/추가다. 검토 기록은 newsroom_review.md에 있다.
공유 대화에서 DAT-01~06 완료로 기록되어 있지만, 기준 데이터 30건 및 표준사전 원본은 로컬에 없고 DB 센터·프로젝트는 각각 0건이다.
전체 Task Backlog 첨부파일은 이 서버에서 확보되지 않았다. task_status.json은 전체 Backlog를 대체하지 않으며, 확인된 범위를 추적한다.

## 2026-09-28 KT Cloud RSS 확장

- `0011_ktcloud_rss_feed` 적용. 현재 Alembic revision/head는 0011이다.
- 공식 기술 블로그가 공개한 RSS를 `LIMITED` 정책으로 등록했다.
- 15개 항목을 처리해 데이터센터 관련 2건을 신규 저장했다.
- 본문·요약문·이미지·첨부파일은 저장하지 않는다.
- LG유플러스·LG CNS·SK브로드밴드는 수집 조건을 확정할 때까지 PENDING/비활성 상태를 유지한다.

## 2026-09-28 LG유플러스 뉴스룸 확장

- `0012_lgu_newsroom_page` 적용. 공식 뉴스룸 HTML 목록용 `source_page`를 추가했다.
- 첫 화면의 보도자료 제목·URL·게시일만 수집한다.
- 최초 실행에서 보도자료 6건을 파싱했으며 데이터센터 관련 항목은 0건이었다.
- 매일 06:50 KST 뉴스룸 수집 타이머를 추가했다.
- LG CNS와 SK브로드밴드는 이용 조건과 안정적인 공개 목록 형식을 더 확인할 때까지 PENDING/비활성 상태다.

## 2026-09-28 SK브로드밴드 보도자료 확장

- `0013_skb_press_page` 적용. 현재 Alembic revision/head는 0013이다.
- 공식 보도자료 목록 첫 페이지의 제목·URL·게시일만 수집한다.
- 상세 기사 본문은 요청하거나 저장하지 않는다.
- 최초 실행에서 목록 11건을 파싱했으며 데이터센터 관련 항목은 0건이었다.
- 기존 06:50 KST 뉴스룸 타이머가 LG유플러스와 SK브로드밴드를 함께 처리한다.
- LG CNS는 목록에서 제목을 얻기 위해 상세 페이지 요청이 필요하고 이용 조건이 불명확해 PENDING/비활성 상태로 유지한다.

## 2026-09-28 LG CNS 자동수집 차단

- 뉴스룸 화면은 `/bin/cf/fetch` 공개 응답으로 제목과 게시일을 불러온다.
- 공식 robots 정책이 `/bin/` 경로를 차단하므로 자동 호출하지 않는다.
- `0014_block_lgcns_automation`에서 `BLOCKED`, `NO_STORAGE`, `DISALLOWED`, 비활성으로 명시했다.
- 상세 페이지를 반복 호출하는 우회 수집도 사용하지 않는다.
- 필요한 LG CNS 근거는 담당자가 공식 페이지를 직접 확인하고 URL만 수동 등록한다.

## 2026-09-29 수집 상태 알림

- `src09_collection_alert.py`는 OpenDART, RSS, 뉴스룸의 가장 최근 실행을 확인한다.
- 최근 실행이 없거나 36시간을 넘겼거나 상태가 SUCCESS가 아니면 종료 코드 2와 함께 경고를 남긴다.
- `COLLECTION_ALERT_WEBHOOK_URL`이 설정된 경우 작업명, 상태, 종료 시각, 실패 출처 수만 전송한다. 오류 본문과 환경변수는 전송하지 않는다.
- 일일 점검 타이머는 07:15 KST에 실행하며 최대 5분 무작위 지연을 적용한다.

```bash
bash src09_install_alert_schedule.sh --enable
.venv/bin/python -B src09_collection_alert.py --no-webhook
```

## 2026-09-29 공개 센터 Export

- `src10_public_export.py`는 `public_visible=true`이면서 검토 상태가 `CONFIRMED`인 센터만 내보낸다.
- CSV와 GeoJSON을 지원하며 지역과 운영 상태로 필터링할 수 있다.
- CSV 수식 실행을 막고 모든 실행 결과를 `export_job`과 `audit_log`에 기록한다.
- 현재 기준 데이터가 반입되지 않아 정상적인 빈 파일이 생성된다.

```bash
.venv/bin/python -B src10_public_export.py --format csv
.venv/bin/python -B src10_public_export.py --format geojson --sido 서울특별시
```

## 2026-09-29 공개 조회 API

- `public_api.py`는 공개 승인된 센터 목록과 지역 요약만 제공하는 읽기 전용 API다.
- DB 연결도 읽기 전용이며 오류 본문과 접속 정보는 응답하지 않는다.
- 로컬 `127.0.0.1:8765`에만 바인딩한다. 외부 공개는 인증·TLS가 있는 reverse proxy를 추가한 뒤 진행한다.

| 경로 | 내용 |
|---|---|
| `/api/v1/healthz` | DB 연결 상태와 API 버전 |
| `/api/v1/sites` | 센터 목록, `sido`, `status`, `page`, `limit` 지원 |
| `/api/v1/sites/{site_code}` | 공개 센터 상세와 프로젝트 |
| `/api/v1/regions` | 공개 센터의 지역·상태별 집계 |
| `/api/v1/companies` | 공개 센터 기준 경쟁사 비교 |
| `/api/v1/yearly` | 공개 프로젝트 연도별 공급 |
| `/api/v1/collection-status` | 오류 본문을 제외한 최근 수집 상태 |

- `/`에서 전국 지도, 센터 목록·상세, 지역·경쟁사·연도별 통계와 수집 운영 화면을 제공한다.
- 지도는 외부 지도 SDK 없이 좌표를 표시하므로 외부 API 키가 필요 없다.

```bash
bash install_public_api_service.sh --enable
curl -s http://127.0.0.1:8765/api/v1/healthz
```

## 2026-09-29 센터 기준 데이터 반입

- `data/site_import_template.csv` 형식으로 센터 데이터를 준비한다.
- `src11_site_import.py`는 필수값, 코드 중복, 좌표 범위와 분류값을 먼저 검증한다.
- 기본 실행은 dry-run이다. `--apply`를 지정해도 신규 행은 `NEEDS_EVIDENCE`, 비공개 상태로만 등록한다.

```bash
.venv/bin/python -B src11_site_import.py data/site_import_template.csv
.venv/bin/python -B src11_site_import.py 준비된파일.csv --apply
```

## 2026-09-30 수집 대상 100개 확장

- 기존 공개·확정 센터 26개는 그대로 유지한다.
- `data/collected_site_targets_20260930.csv`의 신규 후보 74개는 `NEEDS_EVIDENCE`, 비공개 상태로 반입한다.
- 후보 출처는 `DATACENTERMAP_KR`로 등록하며, 공식 사업자 자료를 교차 확인한 뒤 검토 워크플로에서 공개한다.
- 대시보드의 수집 대상 총계는 100개이며 공개 목록과 지도에는 확정된 26개만 표시한다.

```bash
.venv/bin/python src11_site_import.py data/collected_site_targets_20260930.csv
.venv/bin/python src11_site_import.py data/collected_site_targets_20260930.csv --apply
```

## 2026-09-30 수집 대상 200개 확장·지도 보정

- 추가 발굴 후보 100개를 `NEEDS_EVIDENCE`, 비공개 상태로 반입해 전체 수집 대상을 200개로 확장한다.
- 전체 200개 중 공개 확정은 26개, 공식 근거와 세부 위치 검토 대기는 174개다.
- 광역 위치나 기관 단위 후보는 이름에 `수집 검증 대상`을 표시하며, 실제 데이터센터 존재와 주소를 확인한 뒤에만 공개한다.
- Google Maps 링크와 임베드 지도는 좌표보다 표준주소를 우선해 오래된 좌표·행정구역 중심점 오차를 피한다.

## 2026-09-30 DealBook 정보 소스

- 딜북뉴스의 공개 데이터센터 태그 RSS `https://www.dealbook.co.kr/tag/deiteosenteo/rss/`를 데이터센터 PF·투자·자산운용·시공 동향의 후보 근거로 사용한다.
- robots.txt가 차단한 `/bluedot/`, `/p/` 경로는 요청하지 않으며 데이터센터 태그 RSS만 수집한다.
- 제목·정규 URL·게시일·발행기관만 저장하고 본문·요약·이미지는 저장하지 않는다.
- 2차 보도자료인 C등급 출처이므로 센터·용량·참여 관계 공개 전 공식 기업 또는 공공기관 자료와 교차검증한다.

```bash
.venv/bin/python src11_site_import.py data/collected_site_targets_200_20260930.csv
.venv/bin/python src11_site_import.py data/collected_site_targets_200_20260930.csv --apply
```

## 2026-09-29 프로젝트 기준 데이터 반입

- `src12_project_import.py`는 프로젝트 코드·센터 참조·상태·날짜 순서·중복을 검증한다.
- 참조 센터가 N100 DB에 존재하지 않으면 전체 반입을 중단한다.
- 신규 프로젝트는 `NEEDS_EVIDENCE`, 비공개 상태로만 저장한다.

```bash
.venv/bin/python -B src12_project_import.py data/project_import_template.csv
.venv/bin/python -B src12_project_import.py 준비된프로젝트.csv --apply
```

## 2026-09-29 참조 데이터 반입

- `src13_reference_import.py`는 기업, 참여 관계, 용량, 근거 문서 CSV를 각각 검증한다.
- 기업·참여 관계·용량은 `CANDIDATE`, 참여 관계는 비공개, 근거 문서는 `INTERNAL`로 저장한다.
- URL, 날짜, 역할, 범위, 용량 단계·기준, 양수 값과 참조 코드를 검증한다.

```bash
.venv/bin/python -B src13_reference_import.py company data/company_import_template.csv
.venv/bin/python -B src13_reference_import.py participation data/participation_import_template.csv
.venv/bin/python -B src13_reference_import.py capacity data/capacity_import_template.csv
.venv/bin/python -B src13_reference_import.py evidence data/evidence_import_template.csv
```

검증 후 실제 반입할 때만 마지막에 `--apply`를 추가한다.

## 2026-09-29 검토·품질 관리

- `src14_review_workflow.py`는 7개 엔터티의 대기열과 승인·반려를 처리하며 모든 결정을 `audit_log`에 기록한다.
- 공개 플래그는 센터·프로젝트·참여 관계를 승인하면서 `--publish`를 명시한 경우에만 활성화된다.
- `src15_quality_report.py`는 사이트, 프로젝트, 관계, 용량, 근거 최신성과 검토 대기 건수를 읽기 전용으로 점검한다.

```bash
.venv/bin/python -B src14_review_workflow.py queue --json
.venv/bin/python -B src14_review_workflow.py review site UUID approve --note '근거 확인' --publish
.venv/bin/python -B src15_quality_report.py --json dashboard/quality.json --html dashboard/quality.html
```

내부 검토 콘솔은 N100 서버의 `http://127.0.0.1:8766/`에서 제공한다. 관리 토큰과 검토자 이름을 입력하면 대상별 상세정보와 공식 원문을 확인하고 승인 또는 반려할 수 있다. 센터·프로젝트·참여 관계는 승인과 공개를 분리해 선택하며 모든 결정에는 검토 사유가 필요하고 `audit_log`에 기록된다. 서비스는 로컬 인터페이스에만 바인딩하므로 외부에서 사용할 때는 SSH 터널 등 인증된 관리 경로를 사용한다.

## 2026-09-29 사실·백업·내부 운영

- `src16_fact_import.py`는 추출 사실을 `CANDIDATE`로 저장하고 근거 문서와 함께 연결한다.
- `src17_backup.py`는 custom-format 백업, `pg_restore --list` 검증, SHA-256 manifest와 30일 보존 dry-run을 지원한다.
- `internal_api.py`는 32자 이상 Bearer token을 요구하며 로컬 인터페이스에서 검토 대기열·품질 조회·승인 API를 제공한다.
- `src18_service_health.py`는 DB, 공개 API, 수집 타이머, 디스크, 최근 수집 상태를 통합 점검한다.
- `src19_retention.py`는 export 30일, raw 180일, backup 30일 정책을 기본으로 사용하며 `--apply` 전에는 삭제하지 않는다.

```bash
.venv/bin/python -B src16_fact_import.py data/fact_import_template.csv
.venv/bin/python -B src17_backup.py create
.venv/bin/python -B src18_service_health.py --json dashboard/health.json
.venv/bin/python -B src19_retention.py exports --manifest dashboard/retention_preview.json
```
