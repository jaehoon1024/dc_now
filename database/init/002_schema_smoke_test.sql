\set ON_ERROR_STOP on

BEGIN;

-- 가상 물리 센터 1개: 테스트 후 ROLLBACK되므로 실제 DB에는 남지 않습니다.
INSERT INTO dc_site (
    site_id,
    site_code,
    site_name,
    address_raw,
    address_standard,
    sido,
    sigungu,
    location_precision,
    coordinate_quality,
    geom,
    review_status,
    public_visible
) VALUES (
    '00000000-0000-4000-8000-000000000001',
    'SITE-TEST-001',
    '서울 테스트 데이터센터',
    '서울특별시 테스트 주소',
    '서울특별시 중구 테스트로 1',
    '서울특별시',
    '중구',
    'ROAD_ADDRESS',
    'A',
    ST_SetSRID(ST_MakePoint(126.9780, 37.5665), 4326),
    'APPROVED',
    FALSE
);

-- 기존 운영 범위와 같은 부지의 증설 범위를 별도 프로젝트로 입력합니다.
INSERT INTO dc_project (
    project_id,
    project_code,
    site_id,
    project_name,
    project_type,
    project_scope,
    status_code,
    review_status,
    rfs_date,
    completion_date,
    service_start_date,
    public_visible
) VALUES
(
    '00000000-0000-4000-8000-000000000101',
    'PROJ-TEST-OPERATING',
    '00000000-0000-4000-8000-000000000001',
    '기존 운영동 검증 프로젝트',
    'NEW_BUILD',
    '기존 운영 범위의 관계 검증용 가상 프로젝트',
    'OPERATING',
    'APPROVED',
    DATE '2025-01-01',
    DATE '2024-12-01',
    DATE '2025-01-01',
    FALSE
),
(
    '00000000-0000-4000-8000-000000000102',
    'PROJ-TEST-EXPANSION',
    '00000000-0000-4000-8000-000000000001',
    '2동 증설 검증 프로젝트',
    'EXPANSION',
    '같은 부지의 개발 중 증설 범위 검증용 가상 프로젝트',
    'CONSTRUCTION',
    'APPROVED',
    NULL,
    NULL,
    NULL,
    FALSE
);

INSERT INTO project_phase (
    phase_id,
    phase_code,
    project_id,
    phase_name,
    phase_order,
    scope_description,
    status_code,
    review_status,
    construction_start_date,
    rfs_date
) VALUES
(
    '00000000-0000-4000-8000-000000000201',
    'PHASE-TEST-OPERATING',
    '00000000-0000-4000-8000-000000000101',
    '운영 단계',
    1,
    '운영 중인 가상 공급 범위',
    'OPERATING',
    'APPROVED',
    DATE '2023-01-01',
    DATE '2025-01-01'
),
(
    '00000000-0000-4000-8000-000000000202',
    'PHASE-TEST-CONSTRUCTION',
    '00000000-0000-4000-8000-000000000102',
    '증설 1단계',
    1,
    '공사 중인 가상 증설 공급 범위',
    'CONSTRUCTION',
    'APPROVED',
    DATE '2026-01-01',
    NULL
);

-- 정상 관계 조회: 4개 행(프로젝트 2개 x Phase 1개)이 아니라 정확히 2개 행이어야 합니다.
SELECT
    s.site_code,
    p.project_code,
    p.status_code AS project_status,
    ph.phase_code,
    ph.status_code AS phase_status,
    ST_Y(s.geom) AS latitude,
    ST_X(s.geom) AS longitude
FROM dc_site s
JOIN dc_project p ON p.site_id = s.site_id
JOIN project_phase ph ON ph.project_id = p.project_id
WHERE s.site_code = 'SITE-TEST-001'
ORDER BY p.project_code;

-- 잘못된 상태코드가 차단되는지 시험합니다.
DO $$
BEGIN
    BEGIN
        INSERT INTO dc_project (
            project_code,
            site_id,
            project_name,
            project_scope,
            status_code
        ) VALUES (
            'PROJ-TEST-BAD-STATUS',
            '00000000-0000-4000-8000-000000000001',
            '잘못된 상태코드 검증',
            '제약조건 테스트',
            'WRONG_STATUS'
        );
        RAISE EXCEPTION 'FAIL: 잘못된 상태코드가 저장되었습니다.';
    EXCEPTION
        WHEN check_violation THEN
            RAISE NOTICE 'PASS: 잘못된 상태코드가 차단되었습니다.';
    END;
END;
$$;

-- 존재하지 않는 site_id 연결이 차단되는지 시험합니다.
DO $$
BEGIN
    BEGIN
        INSERT INTO dc_project (
            project_code,
            site_id,
            project_name,
            project_scope,
            status_code
        ) VALUES (
            'PROJ-TEST-BAD-FK',
            '00000000-0000-4000-8000-000000009999',
            '잘못된 외래키 검증',
            '제약조건 테스트',
            'IDEA'
        );
        RAISE EXCEPTION 'FAIL: 존재하지 않는 site_id가 저장되었습니다.';
    EXCEPTION
        WHEN foreign_key_violation THEN
            RAISE NOTICE 'PASS: 존재하지 않는 site_id 연결이 차단되었습니다.';
    END;
END;
$$;

-- 테스트 데이터를 모두 제거합니다.
ROLLBACK;

-- 결과가 0이면 테스트 자료가 실제 DB에 남지 않은 것입니다.
SELECT COUNT(*) AS remaining_test_sites
FROM dc_site
WHERE site_code LIKE 'SITE-TEST-%';
