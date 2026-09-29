import unittest
import os

from src12_project_import import import_rows, validate_rows


FIELDS = [
    "project_code", "site_code", "project_name", "project_scope",
    "status_code", "planned_rfs_date", "rfs_date", "completion_date",
    "service_start_date",
]


class ProjectImportTests(unittest.TestCase):
    def test_valid_project_dates_are_parsed(self):
        rows, errors = validate_rows(FIELDS, [{
            "project_code": "PROJ-001", "site_code": "SITE-001",
            "project_name": "1동", "project_scope": "신축",
            "status_code": "OPERATING", "completion_date": "2025-12-01",
            "rfs_date": "2026-01-01", "service_start_date": "2026-01-01",
        }])
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["rfs_date"].isoformat(), "2026-01-01")

    def test_invalid_status_date_order_and_duplicate_are_reported(self):
        raw = {
            "project_code": "PROJ-001", "site_code": "SITE-001",
            "project_name": "1동", "project_scope": "신축",
            "status_code": "BROKEN", "completion_date": "2026-02-01",
            "rfs_date": "2026-01-01",
        }
        _, errors = validate_rows(FIELDS, [raw, raw])
        messages = [error.message for error in errors]
        self.assertIn("허용되지 않은 상태", messages)
        self.assertIn("준공일보다 빠를 수 없음", messages)
        self.assertIn("파일 내 중복", messages)

    def test_missing_required_columns_stop_validation(self):
        _, errors = validate_rows(["project_code"], [])
        self.assertEqual(
            {error.field for error in errors},
            {"site_code", "project_name", "project_scope"},
        )

    @unittest.skipUnless(os.getenv("DC_TEST_DATABASE") == "1", "DB test disabled")
    def test_import_is_private_and_needs_evidence(self):
        from contextlib import contextmanager
        from sqlalchemy import create_engine, text
        from src04_rss_collector import load_env_file, resolve_database_url

        load_env_file()
        engine = create_engine(resolve_database_url())
        try:
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    connection.execute(text("""
                        CREATE TEMP TABLE dc_site (
                            site_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                            site_code varchar(30) UNIQUE NOT NULL,
                            record_status varchar(20) NOT NULL
                        ) ON COMMIT DROP
                    """))
                    connection.execute(text("""
                        CREATE TEMP TABLE dc_project (
                            project_code varchar(30) UNIQUE NOT NULL,
                            site_id uuid NOT NULL, project_name text NOT NULL,
                            project_type text, project_scope text NOT NULL,
                            status_code text, scope_note text,
                            planned_rfs_date date, rfs_date date,
                            completion_date date, service_start_date date,
                            review_status text NOT NULL, public_visible boolean NOT NULL
                        ) ON COMMIT DROP
                    """))
                    connection.execute(text("INSERT INTO dc_site(site_code,record_status) VALUES ('SITE-001','ACTIVE')"))

                    class TestEngine:
                        @contextmanager
                        def begin(self):
                            yield connection

                    rows, errors = validate_rows(FIELDS, [{
                        "project_code": "PROJ-001", "site_code": "SITE-001",
                        "project_name": "1동", "project_scope": "신축",
                        "status_code": "CONSTRUCTION",
                    }])
                    self.assertEqual(errors, [])
                    self.assertEqual(import_rows(TestEngine(), rows), 1)
                    saved = connection.execute(text("SELECT review_status, public_visible FROM dc_project")).one()
                    self.assertEqual(saved.review_status, "NEEDS_EVIDENCE")
                    self.assertFalse(saved.public_visible)
                finally:
                    transaction.rollback()
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
