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
