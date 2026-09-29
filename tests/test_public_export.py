import csv
import json
import tempfile
import unittest
from pathlib import Path

from src10_public_export import (
    build_site_query, safe_csv_value, to_feature, write_csv, write_geojson,
)


class PublicExportTests(unittest.TestCase):
    def test_query_always_limits_export_to_confirmed_public_rows(self):
        query, parameters = build_site_query("서울특별시", "OPERATING")
        self.assertIn("public_visible = true", query)
        self.assertIn("review_status = 'CONFIRMED'", query)
        self.assertEqual(parameters, {"sido": "서울특별시", "status": "OPERATING"})

    def test_csv_values_block_spreadsheet_formulas(self):
        self.assertEqual(safe_csv_value("=HYPERLINK('x')"), "'=HYPERLINK('x')")
        self.assertEqual(safe_csv_value("normal"), "normal")

    def test_writers_create_valid_empty_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "sites.csv"
            geojson_path = Path(directory) / "sites.geojson"
            self.assertEqual(write_csv(csv_path, []), 0)
            self.assertEqual(write_geojson(geojson_path, []), 0)
            with csv_path.open(encoding="utf-8-sig") as handle:
                self.assertTrue(next(csv.reader(handle)))
            self.assertEqual(json.loads(geojson_path.read_text())["features"], [])

    def test_geojson_point_uses_longitude_then_latitude(self):
        feature = to_feature({"site_code": "S1", "latitude": 37.5, "longitude": 127.0})
        self.assertEqual(feature["geometry"]["coordinates"], [127.0, 37.5])
        self.assertNotIn("latitude", feature["properties"])


if __name__ == "__main__":
    unittest.main()
