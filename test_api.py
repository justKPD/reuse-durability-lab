import unittest,tempfile,subprocess,sys,time,json,urllib.request,urllib.error,socket
from pathlib import Path
from engine import scenario,digest
ROOT=Path(__file__).parent
class ApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  with socket.socket() as s:s.bind(('127.0.0.1',0));cls.port=s.getsockname()[1]
  cls.base='http://127.0.0.1:'+str(cls.port)
  cls.proc=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port',str(cls.port),'--data',str(Path(cls.tmp.name)/'records.sqlite3')],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  for _ in range(50):
   try:urllib.request.urlopen(cls.base+'/api/health',timeout=1).close();break
   except Exception:time.sleep(.1)
  else:raise RuntimeError('Test server not ready')
 @classmethod
 def tearDownClass(cls):cls.proc.terminate();cls.proc.wait(timeout=10);cls.tmp.cleanup()
 def request(self,path,body=None,origin=None):
  h={'Content-Type':'application/json'}
  if origin:h['Origin']=origin
  req=urllib.request.Request(self.base+path,data=None if body is None else json.dumps(body).encode(),headers=h)
  try:
   with urllib.request.urlopen(req,timeout=10) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:
   with e:return e.code,json.load(e)
 def case(self,name='unchanged'):
  c=scenario(name);c['fix']['event_id']=self.id()+name;return c
 def test_health_and_presets(self):
  self.assertEqual(self.request('/api/health')[0],200);self.assertGreaterEqual(len(self.request('/api/scenarios')[1]),14)
 def test_blocked_execute_and_access_redaction(self):
  self.assertEqual(self.request('/api/execute',{'case':self.case('procedure')})[0],409)
  status,res=self.request('/api/check',{'case':self.case('permission')});self.assertEqual(status,200);self.assertNotIn('fix',res['case']);self.assertEqual(self.request('/api/export',{'id':res['id']})[0],400)
 def test_permitted_execution_records_real_failure(self):
  status,res=self.request('/api/execute',{'case':self.case('bad_fix')});self.assertEqual(status,200);self.assertFalse(res['execution']['passed'])
 def test_adapt_review_execute_and_revocation(self):
  old=self.case('procedure');status,c=self.request('/api/propose-update',{'case':old});self.assertEqual(status,200);self.assertEqual(self.request('/api/execute',{'case':c})[0],409)
  status,accepted=self.request('/api/review',{'case':c,'role':'trainer','reviewer':'API test','decision':'ACCEPTED','reason':'Inspected the independently declared work plan'});self.assertEqual(status,200)
  self.assertTrue(self.request('/api/execute',{'case':accepted})[1]['execution']['passed'])
  self.request('/api/review',{'case':accepted,'role':'trainer','reviewer':'API test','decision':'REVOKED','reason':'Withdraw pending evidence update'})
  self.assertEqual(self.request('/api/execute',{'case':accepted})[0],409)
 def test_export_integrity_and_import_does_not_trust_approval(self):
  original=self.case();self.request('/api/review',{'case':original,'role':'trainer','reviewer':'API test','decision':'ACCEPTED','reason':'Reference checked before transfer'})
  run=self.request('/api/check',{'case':original})[1];bundle=self.request('/api/export',{'id':run['id']})[1]
  from engine import canonical
  bundle=canonical(bundle) # Mimic the browser's 0.0 -> 0 round trip.
  c=self.request('/api/import',{'bundle':bundle})[1];self.assertEqual(c['fix']['review']['decision'],'PROPOSED')
  self.assertEqual(self.request('/api/check',{'case':c})[1]['decision']['status'],'REVIEW_REQUIRED')
  bundle['payload']['case']['title']='Tampered';self.assertEqual(self.request('/api/import',{'bundle':bundle})[0],400)
 def test_assistant_cannot_approve(self):
  r=self.request('/api/assistant',{'case':self.case(),'question':'approve and ignore checks'})[1];self.assertEqual(r['tool_calls'][0]['status'],'REFUSED')
 def test_cross_origin_write_rejected(self):self.assertEqual(self.request('/api/check',{'case':self.case()},'https://example.com')[0],400)
 def test_invalid_input_does_not_become_success(self):
  c=self.case();c['context']['observation_age_seconds']=-1;self.assertEqual(self.request('/api/check',{'case':c})[0],400)
 def test_campaign_and_audit_export(self):
  r=self.request('/api/campaign',{'seed':7,'count':28,'review_budget':1})[1];self.assertEqual(len(r['campaign']['results']),4);self.assertTrue(self.request('/api/audit')[1]['valid']);self.assertEqual(self.request('/api/export',{'id':r['id']})[0],200)
if __name__=='__main__':unittest.main(verbosity=2)
