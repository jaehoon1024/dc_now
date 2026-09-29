\set ON_ERROR_STOP on

-- 안전장치: 이 롤백은 테스트 DB에서만 실행할 수 있습니다.
SELECT current_database() = 'dc_platform_test' AS is_safe_database \gset

\if :is_safe_database

BEGIN;

-- 외래키의 자식 테이블부터 역순으로 제거합니다.
DROP TABLE IF EXISTS project_phase;
DROP TABLE IF EXISTS dc_project;
DROP TABLE IF EXISTS dc_site;

DROP FUNCTION IF EXISTS set_updated_at();

COMMIT;

\echo 'PASS: dc_platform_test의 핵심 스키마 롤백이 완료되었습니다.'

\else

\echo 'STOP: 이 파일은 dc_platform_test에서만 실행할 수 있습니다.'
\quit 1

\endif
