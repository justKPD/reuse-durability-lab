import unittest,json,urllib.request,urllib.error,http.cookiejar,uuid
BASE='https://reuse-durability-lab.vercel.app'
class PublicTests(unittest.TestCase):
 def setUp(self):
  self.a=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  self.b=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def req(self,client,path,data=None,headers=None):
  r=urllib.request.Request(BASE+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json',**(headers or {})})
  try:
   with client.open(r,timeout=30) as response:return response.status,json.load(response)
  except urllib.error.HTTPError as e:
   with e:
    try:return e.code,json.load(e)
    except Exception:return e.code,{}
 def case(self,client):
  return self.req(client,'/api/scenario?name=unchanged')[1]
 def test_session_records_are_isolated(self):
  c=self.case(self.a);c['fix']['event_id']='public-'+uuid.uuid4().hex
  run=self.req(self.a,'/api/check',{'case':c})[1]
  self.assertEqual(self.req(self.a,'/api/run/'+run['id'])[0],200)
  self.assertEqual(self.req(self.b,'/api/run/'+run['id'])[0],400)
  self.assertNotIn(run['id'],[r['id'] for r in self.req(self.b,'/api/history')[1]])
 def test_review_cannot_cross_session(self):
  c=self.case(self.a);c['fix']['event_id']='public-review-'+uuid.uuid4().hex
  self.assertEqual(self.req(self.a,'/api/review',{'case':c,'role':'trainer','reviewer':'Independent test','decision':'REVOKED','reason':'Session isolation regression test'})[0],200)
  self.assertEqual(self.req(self.a,'/api/check',{'case':c})[1]['decision']['status'],'REVIEW_REQUIRED')
  self.assertEqual(self.req(self.b,'/api/check',{'case':c})[1]['decision']['status'],'ALLOWED')
 def test_cross_origin_write_is_rejected(self):
  self.assertEqual(self.req(self.a,'/api/check',{'case':self.case(self.a)},{'Origin':'https://unrelated.example'})[0],400)
 def test_runtime_sources_are_not_public(self):
  for path in ['/runtime/server.py','/runtime/public_demo.py','/Power_Platform_Proof/PROOF_STATUS.json','/.vercel/project.json']:
   try:
    with urllib.request.urlopen(BASE+path,timeout=20) as response:self.fail('Unexpected public path '+path)
   except urllib.error.HTTPError as e:self.assertEqual(e.code,404)
if __name__=='__main__':unittest.main(verbosity=2)

