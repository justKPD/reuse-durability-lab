from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import argparse,json,os,urllib.parse,copy,socket,uuid
from engine import scenario,SCENARIOS,inspect_case,assess,execute,validate_case,digest,require,propose_update
from storage import Store
from experiments import campaign
ROOT=Path(__file__).parent
class LocalServer(ThreadingHTTPServer):
 allow_reuse_address=False
 def server_bind(self):
  if os.name=='nt':self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
  super().server_bind()
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'web'),**kwargs)
 def end_headers(self):
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','same-origin');super().end_headers()
 def send_json(self,obj,status=200):
  data=json.dumps(obj,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def do_GET(self):
  u=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(u.query)
  try:
   if u.path=='/api/health':return self.send_json({'ok':True,'version':'0.1.0','mode':'single-user local demonstration'})
   if u.path=='/api/scenarios':return self.send_json([{'id':k,'title':v[0],'description':v[1]} for k,v in SCENARIOS.items()])
   if u.path=='/api/scenario':return self.send_json(scenario(q.get('name',['unchanged'])[0]))
   if u.path=='/api/history':return self.send_json(self.server.store.runs())
   if u.path=='/api/audit':return self.send_json(self.server.store.audit())
   if u.path.startswith('/api/run/'):
    run=self.server.store.load(u.path.rsplit('/',1)[-1]);return self.send_json(run)
   if u.path.startswith('/api/'):return self.send_json({'error':'Unknown route'},404)
   return super().do_GET()
  except (ValueError,KeyError) as e:self.send_json({'error':str(e)},400)
 def do_POST(self):
  try:
   origin=self.headers.get('Origin')
   if origin:
    require(urllib.parse.urlsplit(origin).netloc==self.headers.get('Host'),'Cross-origin writes are blocked')
   n=int(self.headers.get('Content-Length','0'));require(0<n<=250000,'Request must be 1 to 250000 bytes');body=json.loads(self.rfile.read(n));require(isinstance(body,dict),'JSON object required')
   path=urllib.parse.urlsplit(self.path).path
   if path=='/api/check':
    res=inspect_case(self.server.store.resolve_review(body['case']));return self.send_json(self.server.store.save_run(res))
   if path=='/api/execute':
    case=self.server.store.resolve_review(body['case']);decision=assess(case)
    if not decision['can_execute']:return self.send_json({'error':'Reuse is not authorized by the selected policy','decision':decision},409)
    res=inspect_case(case);res['execution']=execute(case);res['execution_kind']='Authorized virtual execution, not a physical command';return self.send_json(self.server.store.save_run(res))
   if path=='/api/capture':return self.send_json(self.server.store.capture(body['case']))
   if path=='/api/propose-update':return self.send_json(propose_update(self.server.store.resolve_review(body['case'])))
   if path=='/api/review':
    reviewed=self.server.store.review(body['case'],body['decision'],body['reviewer'],body['reason'],body['role'])
    self.server.store.save_run(inspect_case(reviewed))
    return self.send_json(reviewed)
   if path=='/api/campaign':
    res=campaign(body.get('seed',42),body.get('count',140),body.get('review_budget',20));return self.send_json(self.server.store.save_run({'case':{'title':'Synthetic policy campaign'},'campaign':res}))
   if path=='/api/export':
    run=self.server.store.load(body['id'])
    require(run.get('decision',{}).get('access')!='DENIED','A restricted investigation cannot be exported')
    return self.send_json({'format':'reuse-lab/1','payload':run,'payload_hash':digest(run),'notice':'Integrity hash is not a trusted reviewer signature. Imports require fresh review.'})
   if path=='/api/import':
    bundle=body['bundle'];require(bundle.get('format')=='reuse-lab/1','Unknown bundle format');require(digest(bundle.get('payload'))==bundle.get('payload_hash'),'Bundle integrity mismatch')
    case=copy.deepcopy(bundle['payload']['case']);validate_case(case);case['imported_from_payload_hash']=bundle['payload_hash'];case['fix']['event_id']='import-'+uuid.uuid4().hex[:16];case['fix']['review']['decision']='PROPOSED';case['fix']['review']['reason']='Imported content requires local review; external approval is not trusted.'
    return self.send_json(case)
   if path=='/api/assistant':
    query=body.get('question','');require(isinstance(query,str) and 1<=len(query)<=2000,'Question must be 1 to 2000 characters');case=self.server.store.resolve_review(body['case']);res=inspect_case(case)
    if res['decision']['access']=='DENIED':return self.send_json({'mode':'deterministic local tool assistant','answer':res['decision']['reason'],'tool_calls':[{'tool':'check_access','status':'DENIED'}],'result':res})
    if any(w in query.lower() for w in ['approve','override','ignore','accept']):
     return self.send_json({'mode':'deterministic local tool assistant','answer':'I cannot approve a fix or override a failed check. Use the separate review panel with an explicit reviewer decision.','tool_calls':[{'tool':'review_boundary','status':'REFUSED'}],'result':res})
    failed=[x['check'] for x in res['decision']['checks'] if not x['passed']]
    answer=res['decision']['reason']+' '
    if failed:answer+='Checks needing attention: '+', '.join(failed)+'. '
    answer+='The sandbox '+('passes' if res['current']['passed'] else 'fails')+' its independently specified work plan. Sandbox success cannot resolve missing evidence or permission.'
    return self.send_json({'mode':'deterministic local tool assistant; no LLM call','answer':answer,'tool_calls':[{'tool':'assess_reuse','status':res['decision']['status']},{'tool':'isolated_counterfactual','status':'PASS' if res['current']['passed'] else 'FAIL'}],'result':res})
   return self.send_json({'error':'Unknown route'},404)
  except (ValueError,KeyError,TypeError,json.JSONDecodeError) as e:return self.send_json({'error':str(e)},400)
  except Exception as e:
   print(type(e).__name__,str(e),flush=True);return self.send_json({'error':'The operation failed; no successful outcome is claimed.'},500)
def main():
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8794);p.add_argument('--data',default=str(ROOT/'data'/'investigations.sqlite3'));a=p.parse_args()
 server=LocalServer(('127.0.0.1',a.port),Handler);server.store=Store(a.data)
 print(f'Reuse Lab ready: http://127.0.0.1:{a.port}/',flush=True);server.serve_forever()
if __name__=='__main__':main()
