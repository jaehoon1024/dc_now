import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import src04_rss_collector as rss
import src25_google_news_backfill as backfill

class CollectorTests(unittest.TestCase):
    def test_google_news_source_publisher_is_preserved(self):
        payload = b'''<?xml version="1.0" encoding="UTF-8"?>
        <rss><channel><item><title>AI data center</title>
        <link>https://example.com/article</link><guid>one</guid>
        <pubDate>Wed, 01 Oct 2026 00:00:00 GMT</pubDate>
        <source url="https://publisher.example">Publisher Name</source>
        </item></channel></rss>'''
        items = rss.parse_feed(payload, 10)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["publisher"], "Publisher Name")

    def test_evidence_hash_is_stable_across_overlapping_feeds(self):
        item = {"title":"Data center", "canonical_url":"https://example.com/a", "publisher":"Publisher", "published_at":None}
        base = {"source_code":"NEWS", "source_name":"News", "feed_code":"ONE"}
        with tempfile.TemporaryDirectory() as directory:
            _, first = rss.save_evidence_json(Path(directory), base, item, "ALL", "rss:id")
            _, second = rss.save_evidence_json(Path(directory), {**base,"feed_code":"TWO"}, item, "ALL", "rss:id")
        self.assertEqual(first, second)

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


class GoogleNewsBackfillTests(unittest.TestCase):
    def test_windows_cover_range_without_gap(self):
        from datetime import date
        windows = list(backfill.iter_windows(date(2025, 10, 4), date(2026, 10, 5), 31))
        self.assertEqual(windows[0][0], date(2025, 10, 4))
        self.assertEqual(windows[-1][1], date(2026, 10, 5))
        self.assertTrue(all(left[1] == right[0] for left, right in zip(windows, windows[1:])))

    def test_dated_url_replaces_relative_period(self):
        from datetime import date
        url = (
            "https://news.google.com/rss/search?"
            "q=%22data+center%22+when%3A365d&hl=ko&gl=KR"
        )
        result = backfill.dated_feed_url(url, date(2025, 10, 4), date(2025, 11, 4))
        query = dict(__import__("urllib.parse").parse.parse_qsl(__import__("urllib.parse").parse.urlsplit(result).query))["q"]
        self.assertNotIn("when:365d", query)
        self.assertIn("after:2025-10-04", query)
        self.assertIn("before:2025-11-04", query)

    def test_items_without_date_or_outside_window_are_rejected(self):
        from datetime import date, datetime, timezone
        start, end = date(2026, 1, 1), date(2026, 2, 1)
        self.assertFalse(backfill.in_window({"published_at": None}, start, end))
        self.assertFalse(backfill.in_window({"published_at": datetime(2025, 12, 31, tzinfo=timezone.utc)}, start, end))
        self.assertTrue(backfill.in_window({"published_at": datetime(2026, 1, 31, tzinfo=timezone.utc)}, start, end))

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
