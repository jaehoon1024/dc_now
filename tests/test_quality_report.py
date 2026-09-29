import unittest
from src15_quality_report import CHECKS,QUEUE_TABLES,render_html
class QualityReportTests(unittest.TestCase):
 def test_required_quality_dimensions_exist(self):
  self.assertEqual(set(CHECKS),{"site_quality","project_quality","relation_integrity","capacity_quality","evidence_freshness"})
 def test_all_review_queues_are_summarized(self):self.assertEqual(len(QUEUE_TABLES),7)
 def test_html_escapes_stored_values(self):
  page=render_html({"generated_at":"now","review_queue":{},"checks":{"x":[{"code":"<script>","issue":"bad"}]}});self.assertNotIn("<script>",page);self.assertIn("&lt;script&gt;",page)
if __name__=="__main__":unittest.main()
