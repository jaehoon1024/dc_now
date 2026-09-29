import unittest
from ops_status import render

class StatusTests(unittest.TestCase):
    def test_stored_values_are_escaped(self):
        page = render({'generated_at': 'now', 'sections': {'feeds': [{'name': '<script>alert(1)</script>'}]}})
        self.assertNotIn('<script>alert(1)</script>', page)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
