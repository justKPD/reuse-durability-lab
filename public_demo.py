"""Public, synthetic demo adapter. Per-visitor temporary records; no Microsoft data."""
import os,secrets,time,threading,tempfile,re
from pathlib import Path
from http.cookies import SimpleCookie
from types import SimpleNamespace
from server import Handler as LocalHandler
from storage import Store
_sessions={}
_lock=threading.Lock()
class Busy(Exception):pass

def session_for(cookie):
 jar=SimpleCookie()
 try:jar.load(cookie or '')
 except Exception:pass
 token=jar.get('reuse_demo')
 token=token.value if token else ''
 with _lock:
  now=time.time()
  for key,(created,directory,store) in list(_sessions.items()):
   if now-created>7200:
    directory.cleanup();del _sessions[key]
  if token in _sessions:return token,_sessions[token][2],False
  if len(_sessions)>=96:raise Busy()
  token=secrets.token_hex(24)
  directory=tempfile.TemporaryDirectory(prefix='reuse-public-')
  store=Store(Path(directory.name)/'synthetic.sqlite3')
  _sessions[token]=(now,directory,store)
  return token,store,True

class ServerProxy:
 def __init__(self,base,store):self.base=base;self.store=store
 def __getattr__(self,key):return getattr(self.base,key)

class handler(LocalHandler):
 def end_headers(self):
  token=getattr(self,'new_session',None)
  if token:self.send_header('Set-Cookie','reuse_demo='+token+'; Path=/; HttpOnly; SameSite=Strict; Secure; Max-Age=7200')
  self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
  super().end_headers()
 def _dispatch(self,method):
  self.new_session=None
  if self.path.split('?')[0]=='/api/health':
   return self.send_json({'ok':True,'version':'0.2.0-public-demo','mode':'synthetic visitor sandbox','persistence':'temporary; server restarts clear records'})
  if not self.path.startswith('/api/'):return super().do_GET()
  try:token,store,fresh=session_for(self.headers.get('Cookie'))
  except Busy:return self.send_json({'error':'Demo capacity reached. Try again later.'},503)
  if fresh:self.new_session=token
  original=self.server
  self.server=ServerProxy(original,store)
  try:
   return super().do_POST() if method=='POST' else super().do_GET()
  finally:self.server=original
 def do_GET(self):return self._dispatch('GET')
 def do_POST(self):return self._dispatch('POST')

