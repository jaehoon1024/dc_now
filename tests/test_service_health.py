import unittest
from src18_service_health import TIMERS
class ServiceHealthTests(unittest.TestCase):
 def test_all_collection_timers_are_checked(self):self.assertEqual(len(TIMERS),4);self.assertIn("dc-collection-alert.timer",TIMERS)
if __name__=="__main__":unittest.main()
