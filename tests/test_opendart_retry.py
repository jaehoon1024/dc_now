import unittest
from unittest.mock import patch

import src03_opendart_collector as collector


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return self.payload


class OpenDartRetryTests(unittest.TestCase):
    @patch("src03_opendart_collector.time.sleep")
    @patch("src03_opendart_collector.urlopen")
    def test_html_response_is_retried_without_exposing_body(self, mock_open, _sleep):
        mock_open.side_effect = [_Response(b"<!DOCTYPE html><title>temporary</title>"), _Response(b"PK valid")]
        metrics = collector.Metrics()
        payload = collector.api_get_bytes("corpCode.xml", {"crtfc_key": "secret"}, metrics, 1)
        self.assertEqual(payload, b"PK valid")
        self.assertEqual(mock_open.call_count, 2)

    @patch("src03_opendart_collector.time.sleep")
    @patch("src03_opendart_collector.urlopen")
    def test_repeated_html_response_returns_sanitized_error(self, mock_open, _sleep):
        mock_open.side_effect = [_Response(b"<html>blocked</html>")] * 3
        with self.assertRaisesRegex(collector.CollectorError, "3회 실패") as raised:
            collector.api_get_bytes("corpCode.xml", {"crtfc_key": "secret"}, collector.Metrics(), 1)
        self.assertNotIn("blocked", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
