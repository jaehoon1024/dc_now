import io,json,unittest
from internal_api import make_app
class InternalApiTests(unittest.TestCase):
 def call(self,auth="",path="/missing"):
  got={};app=make_app(None,"x"*32)
  def start(s,h):got["s"]=s
  body=b"".join(app({"HTTP_AUTHORIZATION":auth,"PATH_INFO":path,"REQUEST_METHOD":"GET","wsgi.input":io.BytesIO()},start));return got["s"],json.loads(body) if body.startswith(b"{") else body.decode()
 def test_missing_token_is_rejected(self):self.assertEqual(self.call()[0],"401 Unauthorized")
 def test_valid_token_reaches_router(self):self.assertEqual(self.call("Bearer "+"x"*32)[0],"404 Not Found")
 def test_admin_page_is_available_before_api_auth(self):self.assertEqual(self.call(path="/")[0],"200 OK")
if __name__=="__main__":unittest.main()
