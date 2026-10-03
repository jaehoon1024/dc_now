import io
import json
import unittest

from public_api import make_application, parse_positive_int, site_query


class FakeRepository:
    def health(self):
        return None

    def regions(self):
        return [{"sido": "서울특별시", "site_count": 1}]

    def sites(self, sido, status, limit, offset):
        return ([{"site_code": "SEOUL-01", "sido": sido, "lifecycle_group": status}], 1)

    def site_detail(self, site_code):
        return {"site_code": site_code, "site_name": "테스트", "projects": []} if site_code == "SEOUL-01" else None

    def companies(self):
        return [{"company_name": "테스트사", "site_count": 1}]

    def yearly(self):
        return [{"supply_year": 2026, "project_count": 1}]

    def collection_status(self):
        return [{"job_name": "RSS_DAILY", "run_status": "SUCCESS"}]

    def evidence_summary(self):
        return {"total_document_count": 491, "public_document_count": 480, "confirmed_document_count": 491, "source_count": 20}

    def recent_evidence(self, limit=24):
        return [{"title": "테스트 근거", "source_grade": "C"}][:limit]


def request(app, path, query="", method="GET"):
    captured = {}
    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)
    body = b"".join(app({"PATH_INFO": path, "QUERY_STRING": query, "REQUEST_METHOD": method, "wsgi.input": io.BytesIO()}, start_response))
    return captured, json.loads(body)


class PublicApiTests(unittest.TestCase):
    def setUp(self):
        self.app = make_application(FakeRepository())

    def test_site_query_enforces_public_reviewed_scope(self):
        query, params = site_query("서울특별시", "OPERATING", 20, 0)
        self.assertIn("public_visible = true", query)
        self.assertIn("review_status = 'CONFIRMED'", query)
        self.assertIn("commercial_scope_status='IN_SCOPE'", query)
        self.assertEqual(params["status"], "OPERATING")

    def test_sites_endpoint_parses_filters_and_pagination(self):
        response, payload = request(self.app, "/api/v1/sites", "sido=서울특별시&status=OPERATING&limit=20&page=2")
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["page"], 2)
        self.assertEqual(response["headers"]["X-Content-Type-Options"], "nosniff")

    def test_invalid_parameters_and_methods_are_rejected(self):
        self.assertEqual(request(self.app, "/api/v1/sites", "limit=zero")[0]["status"], "400 Bad Request")
        self.assertEqual(request(self.app, "/api/v1/sites", method="POST")[0]["status"], "405 Method Not Allowed")

    def test_limit_is_capped(self):
        self.assertEqual(parse_positive_int("9999", 100, 500), 500)

    def test_dashboard_data_endpoints(self):
        for path in ("/api/v1/companies", "/api/v1/yearly", "/api/v1/collection-status", "/api/v1/evidence-summary", "/api/v1/recent-evidence", "/api/v1/sites/SEOUL-01"):
            response, payload = request(self.app, path)
            self.assertEqual(response["status"], "200 OK")
            self.assertTrue(payload)

    def test_unknown_site_returns_404(self):
        self.assertEqual(request(self.app, "/api/v1/sites/UNKNOWN")[0]["status"], "404 Not Found")


if __name__ == "__main__":
    unittest.main()
