import io,json,unittest
from internal_api import make_app
class InternalApiTests(unittest.TestCase):
 def call(self,auth="",path="/missing",method="GET",payload=None):
  got={};app=make_app(None,"x"*32)
  def start(s,h):got["s"]=s
  raw=json.dumps(payload or {}).encode()
  body=b"".join(app({"HTTP_AUTHORIZATION":auth,"PATH_INFO":path,"REQUEST_METHOD":method,"CONTENT_LENGTH":str(len(raw)),"wsgi.input":io.BytesIO(raw)},start));return got["s"],json.loads(body) if body.startswith(b"{") else body.decode()
 def test_missing_token_is_rejected(self):self.assertEqual(self.call()[0],"401 Unauthorized")
 def test_valid_token_reaches_router(self):self.assertEqual(self.call("Bearer "+"x"*32)[0],"404 Not Found")
 def test_admin_page_is_available_before_api_auth(self):self.assertEqual(self.call(path="/")[0],"200 OK")
 def test_admin_page_has_review_actions_without_storing_token(self):
  _,page=self.call(path="/");self.assertIn('data-mode="internal"',page);self.assertIn('id="token"',page);self.assertNotIn("localStorage",page);self.assertNotIn("sessionStorage",page)
 def test_private_workspace_history_and_queue_require_auth(self):
  for path in ("/internal/v1/workspace","/internal/v1/review-history","/internal/v1/review-queue"):
   self.assertEqual(self.call(path=path)[0],"401 Unauthorized")
 def test_assets_allowlist_does_not_expose_local_files(self):
  self.assertEqual(self.call(path="/manager.js")[0],"200 OK")
  for path in ("/.env","/../.env","/data.json"):
   self.assertEqual(self.call(path=path)[0],"401 Unauthorized")
 def test_review_conflict_returns_409(self):
  from unittest.mock import patch
  from src14_review_workflow import ReviewConflict
  with patch("internal_api.review",side_effect=ReviewConflict("changed")):
   status,body=self.call("Bearer "+"x"*32,"/internal/v1/review","POST",{"kind":"evidence","record_id":"x","decision":"approve","reviewer":"tester","note":"checked","expected_status":"CANDIDATE"})
  self.assertEqual(status,"409 Conflict");self.assertEqual(body["error"],"review_conflict")
 def test_blank_review_note_is_rejected_before_database_access(self):
  status,body=self.call("Bearer "+"x"*32,"/internal/v1/review","POST",{"kind":"evidence","record_id":"x","decision":"approve","reviewer":"tester","note":" "})
  self.assertEqual(status,"400 Bad Request");self.assertEqual(body["error"],"invalid_request")
if __name__=="__main__":unittest.main()
