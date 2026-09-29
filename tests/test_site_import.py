import unittest

from src11_site_import import validate_rows


class SiteImportTests(unittest.TestCase):
    def test_valid_row_is_normalized_and_stays_private(self):
        rows, errors = validate_rows(
            ["site_code", "site_name", "address_raw", "latitude", "longitude"],
            [{"site_code": "SEOUL-01", "site_name": " 서울 센터 ", "address_raw": "서울시 중구", "latitude": "37.5", "longitude": "127.0"}],
        )
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["site_name"], "서울 센터")
        self.assertEqual(rows[0]["coordinate_quality"], "U")

    def test_invalid_and_duplicate_rows_report_all_errors(self):
        fields = ["site_code", "site_name", "address_raw", "latitude", "longitude", "coordinate_quality"]
        raw = [
            {"site_code": "bad code", "site_name": "", "address_raw": "주소", "latitude": "91", "longitude": "127", "coordinate_quality": "Z"},
            {"site_code": "bad code", "site_name": "센터", "address_raw": "주소"},
        ]
        _, errors = validate_rows(fields, raw)
        self.assertGreaterEqual(len(errors), 4)
        self.assertIn("파일 내 중복", [error.message for error in errors])

    def test_missing_columns_stop_validation(self):
        _, errors = validate_rows(["site_code"], [])
        self.assertEqual({error.field for error in errors}, {"site_name", "address_raw"})


if __name__ == "__main__":
    unittest.main()
