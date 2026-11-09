"""Single-user local investigation persistence; all ledger writes are transactional."""
from pathlib import Path
import sqlite3,json,uuid,datetime
from contextlib import contextmanager
from engine import digest,validate_case,require,execute,semantic_id,content_id,assess
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class Store:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.connect() as db:
   db.executescript('CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, hash TEXT NOT NULL, payload TEXT NOT NULL, created TEXT NOT NULL); CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, payload TEXT NOT NULL, created TEXT NOT NULL); CREATE TABLE IF NOT EXISTS ledger(seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, payload TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL, created TEXT NOT NULL);')
   db.execute('CREATE TABLE IF NOT EXISTS reviews(event_id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, review TEXT NOT NULL)')
 @contextmanager
 def connect(self):
  db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
  try:
   with db:yield db
  finally:db.close()
 def append(self,db,kind,payload):
  row=db.execute('SELECT hash FROM ledger ORDER BY seq DESC LIMIT 1').fetchone();previous=row['hash'] if row else 'GENESIS';stamp=now()
  value={'kind':kind,'payload':payload,'previous':previous,'created':stamp}
  db.execute('INSERT INTO ledger(kind,payload,previous,hash,created) VALUES(?,?,?,?,?)',(kind,json.dumps(payload,sort_keys=True),previous,digest(value),stamp))
 def capture(self,case):
  validate_case(case);event_id=case['fix']['event_id'];h=digest(case)
  with self.connect() as db:
   db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT * FROM events WHERE id=?',(event_id,)).fetchone()
   if old:
    require(old['hash']==h,'Event ID already exists with different content. Use a new event ID for a new capture.')
    return {'id':event_id,'duplicate':True,'case_hash':h}
   db.execute('INSERT INTO events VALUES(?,?,?,?)',(event_id,h,json.dumps(case),now()));self.append(db,'CAPTURE',{'event_id':event_id,'case_hash':h})
  return {'id':event_id,'duplicate':False,'case_hash':h}
 def save_run(self,payload):
  identity=uuid.uuid4().hex[:16];payload=dict(payload,id=identity,created=now())
  with self.connect() as db:
   db.execute('BEGIN IMMEDIATE');db.execute('INSERT INTO runs VALUES(?,?,?)',(identity,json.dumps(payload),payload['created']));self.append(db,'RUN',{'run_id':identity,'payload_hash':digest(payload)})
  return payload
 def runs(self):
  with self.connect() as db:rows=db.execute('SELECT id,payload,created FROM runs ORDER BY created DESC LIMIT 50').fetchall()
  return [{'id':r['id'],'title':json.loads(r['payload']).get('case',{}).get('title','Custom case'),'created':r['created'],'decision':json.loads(r['payload']).get('decision',{}).get('status')} for r in rows]
 def load(self,identity):
  with self.connect() as db:row=db.execute('SELECT payload FROM runs WHERE id=?',(identity,)).fetchone()
  if not row:raise KeyError('Run not found')
  return json.loads(row['payload'])
 def review(self,case,decision,reviewer,reason,role):
  validate_case(case);require(role in ['trainer','engineer'],'Only trainer or engineer demo role can review')
  require(decision in ['ACCEPTED','REJECTED','REVOKED'],'Invalid review decision');require(isinstance(reason,str) and 8<=len(reason)<=2000,'Give a meaningful review reason (8 to 2000 characters)');require(isinstance(reviewer,str) and 1<=len(reviewer)<=100,'Reviewer name required')
  if decision=='ACCEPTED':
   require(case.get('original_plan') is not None and case.get('original_context') is not None,'Original plan and observations required for an acceptance')
   original={'fix':case['fix'],'context':case['original_context'],'plan':case['original_plan']}
   require(digest(case['fix']['source'])==case['fix']['source_hash'],'Changed source must be recaptured before acceptance')
   require(execute(original)['passed'],'Original reference execution fails; fix actions before accepting')
   require(semantic_id(case['original_plan'])==case['fix']['scope']['semantic_id'],'Accepted scope must match the original reference plan')
  case=json.loads(json.dumps(case));case['fix']['review']={'decision':decision,'reviewer':reviewer,'role':role,'reason':reason,'time':now()}
  if decision=='ACCEPTED':
   case['fix']['reviewed_content_hash']=content_id(case['fix'])
   original=dict(case,context=case['original_context'],plan=case['original_plan'])
   require(assess(original)['status']=='ALLOWED','Original evidence prerequisites do not support acceptance')
  with self.connect() as db:
   db.execute('BEGIN IMMEDIATE');db.execute('INSERT OR REPLACE INTO reviews VALUES(?,?,?)',(case['fix']['event_id'],content_id(case['fix']),json.dumps(case['fix']['review'])))
   self.append(db,'REVIEW',{'event_id':case['fix']['event_id'],'decision':decision,'role':role,'reviewer':reviewer,'reason':reason,'reviewed_case_hash':digest(case)})
  return case
 def resolve_review(self,case):
  validate_case(case);case=json.loads(json.dumps(case))
  with self.connect() as db:row=db.execute('SELECT * FROM reviews WHERE event_id=?',(case['fix']['event_id'],)).fetchone()
  if row:
   case['fix']['review']=json.loads(row['review'])
   if row['content_hash']!=content_id(case['fix']):case['fix']['review']['decision']='PROPOSED';case['fix']['review']['reason']='Edited content differs from the persisted review.'
   else:case['fix']['reviewed_content_hash']=row['content_hash']
  return case
 def audit(self):
  with self.connect() as db:rows=db.execute('SELECT * FROM ledger ORDER BY seq').fetchall()
  previous='GENESIS';valid=True
  for r in rows:
   obj={'kind':r['kind'],'payload':json.loads(r['payload']),'previous':r['previous'],'created':r['created']}
   if r['previous']!=previous or digest(obj)!=r['hash']:valid=False
   previous=r['hash']
  return {'valid':valid,'events':len(rows),'head':previous,'limitation':'Hash chaining detects content edits relative to the current chain, not privileged replacement of the whole database.'}
