# 재해 복구 절차

1. `systemctl --user stop dc-public-api dc-internal-api`로 쓰기·조회 진입점을 중지한다.
2. `data/backups`에서 `verified: true`인 최신 manifest와 동일 이름의 dump를 선택한다.
3. `src17_backup.py verify 백업경로`로 체크섬과 복구 목록을 다시 확인한다.
4. 별도 복구 DB를 생성하고 `pg_restore --no-owner --no-acl --dbname 복구DB 백업파일`로 복원한다.
5. Alembic revision, PostGIS, 주요 테이블 건수와 공개 범위를 확인한다.
6. 애플리케이션의 DB 접속 대상을 복구 DB로 전환한 후 공개·내부 API를 순서대로 시작한다.
7. `src18_service_health.py`와 `src20_release_check.py`가 성공한 뒤 수집 타이머를 재개한다.

운영 DB에 직접 덮어쓰지 않는다. 비밀번호와 접속 문자열은 명령 이력이나 보고서에 기록하지 않는다.
