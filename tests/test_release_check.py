import unittest
from src20_release_check import evaluate
class ReleaseCheckTests(unittest.TestCase):
 def test_all_checks_are_required(self):self.assertTrue(evaluate([1],[1],[1],True,True)["ready"]);self.assertFalse(evaluate([1],[1],[0],True,True)["ready"])
if __name__=="__main__":unittest.main()
