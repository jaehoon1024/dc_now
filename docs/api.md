# API 운영 명세

## 공개 API `127.0.0.1:8765`

- `GET /` 공개 대시보드
- `GET /api/v1/healthz` 상태
- `GET /api/v1/sites` 공개 승인 센터 목록
- `GET /api/v1/sites/{site_code}` 센터 상세
- `GET /api/v1/regions`, `/companies`, `/yearly`, `/collection-status` 집계

## 내부 API `127.0.0.1:8766`

- `GET /` 내부 검토 콘솔. 대상 상세·원문 링크·품질 현황을 확인하고 승인·반려한다.
- `GET /internal/v1/review-queue` 검토 대기열
- `GET /internal/v1/quality` 품질 보고서
- `POST /internal/v1/review` 승인·반려

내부 API 요청은 `Authorization: Bearer …` 헤더가 필요하다. 오류 응답에는 DB 오류나 비밀값을 포함하지 않는다.
관리 콘솔의 토큰과 검토자 이름은 브라우저 저장소에 기록하지 않는다. 센터·프로젝트·참여 관계는 승인 시 공개 여부를 별도로 선택하며, 검토 사유는 필수다.

## 담당자 중심 화면 (2026-10-13)

공개 API 루트와 GitHub Pages는 동일한 `dashboard/manager.html` 화면을 사용한다.
`/manager.css`, `/manager-core.js`, `/manager.js`만 정적 자산으로 제공하며 임의 파일 경로를 허용하지 않는다.
`GET /data.json`은 공개 원장·집계·공개 승인 상세만 반환한다.

내부 API 루트는 같은 화면의 담당자 모드다. 토큰과 검토자 이름을 입력하면 실제 검토 업무에 연결한다.
토큰은 메모리에만 유지하며 연결 성공 시 입력란을 비운다.

추가 내부 엔드포인트:

- `GET /internal/v1/workspace`: 담당자 화면의 실제 원장 스냅샷 및 공개 스냅샷 생성 시각
- `GET /internal/v1/review-history`: 최근 승인·반려 감사 이력, 최대 100건
- 기존 `POST /internal/v1/review`에 `expected_status`를 전달하면 이미 상태가 변경된 레코드는 `409 review_conflict`로 거부한다.

레코드 승인·반려를 수행하며, 추출 사실 승인만으로 임의의 원장 필드를 자동 수정하지 않는다.
내부 대기 문서와 감사 이력은 정적 공개 데이터에 포함하지 않는다.

공개 센터 상세의 `phases`는 공개·확정 프로젝트에 속한 확정 Phase만 반환한다.
`capacities`는 확정 용량 중 공개 승인된 근거 문서 URL에 연결된 수전·계약전력·IT Load·발표용량만 반환한다.
공개되지 않은 프로젝트, 미확정 Phase, 내부 근거에 연결된 용량은 상세 응답에서 제외한다.
