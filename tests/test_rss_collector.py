import unittest
from pathlib import Path
from unittest.mock import patch
import src04_rss_collector as rss

class CollectorTests(unittest.TestCase):
    def test_unchanged_feed_succeeds_and_observes_interval(self):
        self.check_feeds(False)

    def test_failed_feed_still_observes_interval(self):
        self.check_feeds(True)

    def check_feeds(self, fail):
        feeds = [dict(source_id="s", source_code="S", source_name="source",
                      feed_id=str(i), feed_code=str(i), request_interval_seconds=15)
                 for i in range(2)]
        with patch.object(rss, "create_source_run", return_value="run"), \
             patch.object(rss, "fetch_feed") as fetch, \
             patch.object(rss, "mark_feed_success") as success, \
             patch.object(rss, "mark_feed_failed") as failure, \
             patch.object(rss, "finish_source_run"), \
             patch.object(rss.time, "sleep") as sleep:
            fetch.return_value = (304, b"", None, None, "")
            if fail:
                fetch.side_effect = rss.CollectorError("test failure")
            result = rss.collect_source(None, "run", feeds, Path("/tmp"), 10)
            self.assertEqual(result.successful_feeds, 0 if fail else 2)
            self.assertEqual(result.failed_feeds, 2 if fail else 0)
            self.assertEqual(success.call_count, 0 if fail else 2)
            self.assertEqual(failure.call_count, 2 if fail else 0)
            sleep.assert_called_once_with(15.0)

if __name__ == "__main__":
    unittest.main()

class DatabaseRegressionTests(unittest.TestCase):
    @unittest.skipUnless(__import__('os').getenv('DC_TEST_DATABASE') == '1', 'set DC_TEST_DATABASE=1 for rollback-only DB test')
    def test_missing_publication_date_and_304_preserve_timestamp(self):
        from contextlib import contextmanager
        from datetime import datetime, timezone
        from sqlalchemy import create_engine, text
        rss.load_env_file()
        engine = create_engine(rss.resolve_database_url())
        try:
            with engine.connect() as conn:
                transaction = conn.begin()
                try:
                    conn.execute(text('CREATE TEMP TABLE source_feed (feed_id text, etag text, last_modified text, last_polled_at timestamptz, last_success_at timestamptz, last_item_published_at timestamptz, consecutive_failure_count integer, last_error text) ON COMMIT DROP'))
                    conn.execute(text("INSERT INTO source_feed (feed_id,consecutive_failure_count,last_error) VALUES ('test',2,'old failure')"))
                    class TestEngine:
                        @contextmanager
                        def begin(self):
                            yield conn
                    rss.mark_feed_success(TestEngine(), 'test', None, None, [])
                    row = conn.execute(text('SELECT * FROM source_feed')).mappings().one()
                    self.assertIsNone(row['last_item_published_at'])
                    self.assertEqual(row['consecutive_failure_count'], 0)
                    self.assertIsNone(row['last_error'])
                    published = datetime(2026, 9, 28, tzinfo=timezone.utc)
                    rss.mark_feed_success(TestEngine(), 'test', 'tag', None, [{'published_at': published}])
                    rss.mark_feed_success(TestEngine(), 'test', None, None, [])
                    row = conn.execute(text('SELECT * FROM source_feed')).mappings().one()
                    self.assertEqual(row['last_item_published_at'], published)
                    self.assertEqual(row['etag'], 'tag')
                finally:
                    transaction.rollback()
        finally:
            engine.dispose()
