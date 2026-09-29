BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

-- 물리적인 데이터센터 부지·시설 마스터
CREATE TABLE dc_site (
    site_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_code VARCHAR(30) NOT NULL UNIQUE,
    site_name VARCHAR(200) NOT NULL,
    site_name_raw VARCHAR(200),
    address_raw TEXT NOT NULL,
    address_standard TEXT,
    sido VARCHAR(50),
    sigungu VARCHAR(50),
    location_precision VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
    coordinate_quality CHAR(1) NOT NULL DEFAULT 'U'
        CHECK (coordinate_quality IN ('A', 'B', 'C', 'D', 'U')),
    geom GEOMETRY(POINT, 4326),
    review_status VARCHAR(30) NOT NULL DEFAULT 'NEEDS_EVIDENCE',
    record_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (record_status IN ('ACTIVE', 'INACTIVE')),
    public_visible BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

-- 데이터센터 신축·증설·전환 프로젝트
CREATE TABLE dc_project (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_code VARCHAR(30) NOT NULL UNIQUE,
    site_id UUID NOT NULL REFERENCES dc_site(site_id) ON DELETE RESTRICT,
    project_name VARCHAR(200) NOT NULL,
    project_type VARCHAR(30),
    project_scope TEXT NOT NULL,
    status_code VARCHAR(30)
        CHECK (
            status_code IS NULL OR status_code IN (
                'IDEA',
                'SITE_SECURED',
                'PERMITTING',
                'POWER_SECURED',
                'CONSTRUCTION',
                'READY',
                'OPERATING',
                'ON_HOLD',
                'CANCELLED'
            )
        ),
    review_status VARCHAR(30) NOT NULL DEFAULT 'NEEDS_EVIDENCE',
    scope_note TEXT,
    planned_rfs_date DATE,
    rfs_date DATE,
    completion_date DATE,
    service_start_date DATE,
    public_visible BOOLEAN NOT NULL DEFAULT FALSE,
    record_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (record_status IN ('ACTIVE', 'INACTIVE')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

-- 프로젝트 안에서 공식적으로 구분된 공급 단계
CREATE TABLE project_phase (
    phase_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phase_code VARCHAR(30) NOT NULL UNIQUE,
    project_id UUID NOT NULL REFERENCES dc_project(project_id) ON DELETE RESTRICT,
    phase_name VARCHAR(200) NOT NULL,
    phase_order INTEGER CHECK (phase_order IS NULL OR phase_order >= 1),
    scope_description TEXT NOT NULL,
    status_code VARCHAR(30)
        CHECK (
            status_code IS NULL OR status_code IN (
                'IDEA',
                'SITE_SECURED',
                'PERMITTING',
                'POWER_SECURED',
                'CONSTRUCTION',
                'READY',
                'OPERATING',
                'ON_HOLD',
                'CANCELLED'
            )
        ),
    review_status VARCHAR(30) NOT NULL DEFAULT 'NEEDS_EVIDENCE',
    construction_start_date DATE,
    planned_rfs_date DATE,
    rfs_date DATE,
    completion_date DATE,
    service_start_date DATE,
    record_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (record_status IN ('ACTIVE', 'INACTIVE')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_dc_site_geom
    ON dc_site USING GIST (geom);

CREATE INDEX idx_dc_project_site_id
    ON dc_project (site_id);

CREATE INDEX idx_dc_project_status_code
    ON dc_project (status_code);

CREATE INDEX idx_project_phase_project_id
    ON project_phase (project_id);

CREATE INDEX idx_project_phase_status_code
    ON project_phase (status_code);

-- 데이터 수정 시 updated_at을 자동으로 갱신
CREATE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dc_site_updated_at
BEFORE UPDATE ON dc_site
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_dc_project_updated_at
BEFORE UPDATE ON dc_project
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_project_phase_updated_at
BEFORE UPDATE ON project_phase
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE dc_site OWNER TO dc_app;
ALTER TABLE dc_project OWNER TO dc_app;
ALTER TABLE project_phase OWNER TO dc_app;
ALTER FUNCTION set_updated_at() OWNER TO dc_app;

COMMIT;
