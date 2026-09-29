import unittest
from datetime import datetime, timedelta, timezone

from src09_collection_alert import EXPECTED_JOBS, build_payload, evaluate_runs


class CollectionAlertTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)

    def healthy_run(self):
        return {
            "run_status": "SUCCESS",
            "started_at": self.now - timedelta(hours=2),
            "finished_at": self.now - timedelta(hours=1),
            "failed_source_count": 0,
        }

    def test_all_recent_successes_are_healthy(self):
        latest = {job: self.healthy_run() for job in EXPECTED_JOBS}
        self.assertEqual(evaluate_runs(latest, self.now, timedelta(hours=36)), [])

    def test_missing_failed_and_stale_jobs_are_reported(self):
        latest = {
            "RSS_DAILY": {
                **self.healthy_run(),
                "run_status": "PARTIAL",
                "failed_source_count": 1,
            },
            "NEWSROOM_DAILY": {
                **self.healthy_run(),
                "finished_at": self.now - timedelta(hours=40),
            },
        }
        alerts = evaluate_runs(latest, self.now, timedelta(hours=36))
        self.assertEqual(
            [(item.job_name, item.reason) for item in alerts],
            [
                ("OPENDART_DAILY", "NO_RUN"),
                ("RSS_DAILY", "UNHEALTHY_STATUS"),
                ("NEWSROOM_DAILY", "STALE"),
            ],
        )

    def test_payload_excludes_error_messages_and_credentials(self):
        latest = {job: self.healthy_run() for job in EXPECTED_JOBS}
        latest["RSS_DAILY"]["run_status"] = "FAILED"
        latest["RSS_DAILY"]["error_summary"] = "password=secret"
        payload = build_payload(
            evaluate_runs(latest, self.now, timedelta(hours=36)), self.now
        )
        serialized = str(payload)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("error_summary", serialized)


if __name__ == "__main__":
    unittest.main()
