"""Pure comparison policy and an independently specified virtual assembly executor."""
from __future__ import annotations
import copy,hashlib,json,math

VERSION='0.1.0'
ROLES=['operator','trainer','engineer','visitor']
POLICIES=['accepted_only','exact_revision','semantic_rules','durability_gate']
def canonical(obj):
 # JSON in a browser does not preserve the distinction between 0.0 and 0.
 # Normalize equivalent finite numeric values before hashing round-tripped evidence.
 if type(obj)==float:
  if not math.isfinite(obj):raise ValueError('Non-finite values cannot be hashed')
  return int(obj) if obj.is_integer() else obj
 if isinstance(obj,dict):return {k:canonical(v) for k,v in obj.items()}
 if isinstance(obj,list):return [canonical(v) for v in obj]
 return obj
def digest(obj):return hashlib.sha256(json.dumps(canonical(obj),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def content_id(f):return digest({k:f[k] for k in ['id','title','explanation','source','source_hash','scope','actions']})
def require(ok,message):
 if not ok:raise ValueError(message)
def number(v,lo,hi,name):require(type(v) in (int,float) and math.isfinite(v) and lo<=v<=hi,f'{name} must be finite in [{lo}, {hi}]')
def mapping(obj,name):require(isinstance(obj,dict),f'{name} must be an object')

def default_plan():
 return {'id':'work-plan-A','revision':'P1','family':'teaching-fixture','equipment_revision':'E1',
 'procedure':{'sequence':[0,2,1,3],'minimum_effort':0.45,'maximum_effort':0.65,'seal_required':True},
 'documentation_revision':'D1','note':'Independently authored training fixture. Effort is dimensionless.'}
def semantic_id(plan):return digest({'family':plan['family'],'equipment_revision':plan['equipment_revision'],'procedure':plan['procedure']})
def actions_for(plan):
 proc=plan['procedure']
 return [{'op':'isolate'},{'op':'seat'},{'op':'seal','present':True}]+[{'op':'fasten','index':i,'effort':round((proc['minimum_effort']+proc['maximum_effort'])/2,4)} for i in proc['sequence']]+[{'op':'inspect'}]
def default_context():
 return {'task_id':'task-002','station':'Station B','family':'teaching-fixture','equipment_revision':'E1','procedure_revision':'P1',
 'documentation_revision':'D1','work_record_revision':'W1','authoritative_record_revision':'W1','observed_seal':True,
 'observation_age_seconds':10,'observation_quality':'GOOD','role':'operator','evidence_conflict':False,'source_available':True}
def default_fix():
 p=default_plan()
 f={'id':'FIX-001','event_id':'capture-001','title':'Seat the insert, verify the seal, then alternate fasteners',
 'explanation':'A learner advanced to fastening before confirming the seal. Capture the correction and its conditions.',
 'source':{'id':'OBS-001','revision':'1','station':'Station A','text':'Declared virtual teaching fixture, observed seat and seal before fastening.'},
 'scope':{'family':p['family'],'equipment_revision':p['equipment_revision'],'procedure_revision':'P1','documentation_revision':'D1',
 'semantic_id':semantic_id(p),'maximum_observation_age_seconds':120,'allowed_roles':['operator','trainer','engineer']},
 'actions':actions_for(p),'review':{'decision':'ACCEPTED','reviewer':'Demo trainer','role':'trainer','reason':'Virtual reference run passed on the original declared work plan.'}}
 f['source_hash']=digest(f['source'])
 f['reviewed_content_hash']=content_id(f)
 return f
def validate_plan(p):
 mapping(p,'plan')
 for k in ['id','revision','family','equipment_revision','documentation_revision']:require(isinstance(p.get(k),str) and 0<len(p[k])<200,f'plan.{k} required')
 pr=p.get('procedure');mapping(pr,'procedure')
 require(isinstance(pr.get('sequence'),list) and sorted(pr['sequence'])==[0,1,2,3] and all(type(x)==int for x in pr['sequence']),'sequence must permute fasteners 0,1,2,3')
 number(pr.get('minimum_effort'),0,1,'minimum effort');number(pr.get('maximum_effort'),0,1,'maximum effort')
 require(pr['minimum_effort']<pr['maximum_effort'],'effort interval must have positive width')
 require(type(pr.get('seal_required'))==bool,'seal_required must be boolean')
def validate_context(c):
 mapping(c,'context')
 for k in ['task_id','station','family','equipment_revision','procedure_revision','documentation_revision','work_record_revision','authoritative_record_revision']:
  require(isinstance(c.get(k),str) and 0<len(c[k])<200,f'context.{k} required')
 require(c.get('role') in ROLES,'unknown demo role')
 require(c.get('observed_seal') is None or type(c.get('observed_seal'))==bool,'observed_seal must be boolean or null')
 require(c.get('observation_quality') in ['GOOD','BAD','MISSING'],'unknown observation quality')
 for k in ['evidence_conflict','source_available']:require(type(c.get(k))==bool,f'{k} must be boolean')
 number(c.get('observation_age_seconds'),0,1e8,'observation age')
def validate_actions(actions):
 require(isinstance(actions,list) and 1<=len(actions)<=40,'actions must contain 1 to 40 steps')
 for a in actions:
  mapping(a,'action');require(a.get('op') in ['isolate','seat','seal','fasten','inspect'],'unknown action')
  if a['op']=='fasten':
   require(type(a.get('index'))==int and 0<=a['index']<=3,'fastener index must be 0 to 3');number(a.get('effort'),0,1,'effort')
  if a['op']=='seal':require(type(a.get('present'))==bool,'seal action requires present boolean')
def validate_fix(f):
 mapping(f,'fix')
 for k in ['id','event_id','title','explanation','source_hash']:require(isinstance(f.get(k),str) and 0<len(f[k])<5000,f'fix.{k} required')
 mapping(f.get('source'),'source');require(len(json.dumps(f['source']))<20000,'source too large')
 scope=f.get('scope');mapping(scope,'scope')
 for k in ['family','equipment_revision','procedure_revision','documentation_revision','semantic_id']:require(isinstance(scope.get(k),str) and 0<len(scope[k])<200,f'scope.{k} required')
 require(isinstance(scope.get('allowed_roles'),list) and 0<len(scope['allowed_roles'])<=len(ROLES) and all(x in ROLES for x in scope['allowed_roles']),'invalid allowed roles')
 number(scope.get('maximum_observation_age_seconds'),0,86400,'maximum observation age')
 review=f.get('review');mapping(review,'review');require(review.get('decision') in ['PROPOSED','ACCEPTED','REJECTED','REVOKED'],'unknown review decision')
 require(review.get('role') in ['trainer','engineer'],'review requires trainer or engineer demo role')
 require(isinstance(review.get('reviewer'),str) and bool(review['reviewer']),'reviewer required')
 validate_actions(f.get('actions'))
def validate_case(case):
 mapping(case,'case');validate_fix(case.get('fix'));validate_context(case.get('context'));validate_plan(case.get('plan'))
 require(case['context']['family']==case['plan']['family'],'context family must match current work plan')
 require(case['context']['equipment_revision']==case['plan']['equipment_revision'],'context equipment must match current work plan')
 require(case['context']['procedure_revision']==case['plan']['revision'],'context procedure must match current work plan')
 require(case['context']['documentation_revision']==case['plan']['documentation_revision'],'context documentation revision must match current work plan')

def assess(case,policy='durability_gate'):
 validate_case(case);require(policy in POLICIES,'unknown policy')
 f,c,p=case['fix'],case['context'],case['plan'];s=f['scope'];checks=[]
 def ck(name,ok,detail):checks.append({'check':name,'passed':ok,'detail':detail})
 def result(status,why,access='ALLOWED'):
  return {'status':status,'access':access,'technical_status':None if access=='DENIED' else status,'reason':why,'checks':checks,
   'policy':policy,'engine_version':VERSION,'case_hash':digest(case),'plan_hash':digest(p),'fix_hash':digest(f),'can_execute':status=='ALLOWED' and access=='ALLOWED'}
 # All experimental policies share access enforcement. It must not be counted as a technical failure.
 if c['role'] not in s['allowed_roles']:return result('ACCESS_DENIED','Selected demo role is not permitted to retrieve or execute this fix. Technical applicability was not assessed.','DENIED')
 ck('review',f['review']['decision']=='ACCEPTED','Acceptance is scoped; it does not guarantee future applicability.')
 if f['review']['decision']!='ACCEPTED':return result('REVIEW_REQUIRED','No current accepted review authorizes reuse.')
 if policy=='accepted_only':return result('ALLOWED','Baseline reuses any accepted fix, without context invalidation.')
 ck('family',c['family']==s['family'],'Equipment family must be inside the accepted scope.')
 if c['family']!=s['family']:return result('INAPPLICABLE','The current fixture family is outside the accepted scope.')
 if policy=='exact_revision':
  equal=all(c[k]==s[k] for k in ['equipment_revision','procedure_revision','documentation_revision'])
  ck('exact_revisions',equal,'Strict revision baseline requests review even for harmless documentation changes.')
  return result('ALLOWED' if equal else 'REVIEW_REQUIRED','Exact revisions match.' if equal else 'At least one revision changed.')
 # semantic_rules and durability_gate both use the simple authoritative semantic rule.
 equivalent=semantic_id(p)==s['semantic_id']
 ck('semantic_scope',equivalent,'Current authoritative procedure and equipment compared with the accepted scope.')
 if not equivalent:return result('REVIEW_REQUIRED','The procedure or equipment meaning changed; a new review is required.')
 if policy=='semantic_rules':return result('ALLOWED','Simple semantic-equivalence baseline passes; evidence freshness is not checked.')
 ck('source_available',c['source_available'],'Required source evidence must be available.')
 ck('source_hash',digest(f['source'])==f['source_hash'],'Retained source must match its recorded digest.')
 if not c['source_available'] or digest(f['source'])!=f['source_hash']:return result('INSUFFICIENT_EVIDENCE','Source evidence is missing or its identity changed.')
 ck('reviewed_content',f.get('reviewed_content_hash')==content_id(f),'Acceptance must refer to this exact fix content, actions and scope.')
 if f.get('reviewed_content_hash')!=content_id(f):return result('REVIEW_REQUIRED','Fix content changed after the recorded acceptance. Review the changed fix.')
 ck('conflicts',not c['evidence_conflict'],'Conflicting accepted observations cannot be resolved by relevance alone.')
 if c['evidence_conflict']:return result('REVIEW_REQUIRED','Conflicting evidence requires an expert decision.')
 ck('work_record',c['work_record_revision']==c['authoritative_record_revision'],'Mock work-record revision must reconcile with the current authority.')
 if c['work_record_revision']!=c['authoritative_record_revision']:return result('REVIEW_REQUIRED','The mock work record and current authority disagree.')
 quality=c['observation_quality']=='GOOD' and c['observation_age_seconds']<=s['maximum_observation_age_seconds']
 ck('observation',quality,'Required observation must have GOOD quality and be within its declared age limit.')
 if not quality:return result('INSUFFICIENT_EVIDENCE','Observation is stale, missing or low quality.')
 ck('seal_observed',c['observed_seal'] is not None,'Missing a required observation is different from observing absence.')
 if p['procedure']['seal_required'] and c['observed_seal'] is None:return result('INSUFFICIENT_EVIDENCE','Seal observation is missing; do not infer its state.')
 if p['procedure']['seal_required'] and c['observed_seal'] is False:return result('INAPPLICABLE','The seal prerequisite is not satisfied. Resolve the physical condition first.')
 return result('ALLOWED','Accepted scope, current work plan and available observations support reuse. Execution checks remain independent.')

def execute(case,actions=None):
 """Independent virtual process oracle. Never reads accepted scope or review status."""
 validate_case(case);p=case['plan'];c=case['context'];actions=copy.deepcopy(actions if actions is not None else case['fix']['actions']);validate_actions(actions)
 pr=p['procedure'];state={'isolated':False,'seated':False,'seal':False,'fasteners':[0.0]*4,'sequence':[],'inspected':False};trace=[];checks=[]
 for index,a in enumerate(actions):
  before=copy.deepcopy(state);issues=[];op=a['op']
  if op=='isolate':state['isolated']=True
  elif op=='seat':
   if not state['isolated']:issues.append('isolation_before_seating')
   state['seated']=True
  elif op=='seal':
   if not state['seated']:issues.append('seat_before_seal')
   state['seal']=a['present']
   if c['observed_seal'] is False and a['present']:issues.append('seal_not_available')
  elif op=='fasten':
   if not state['isolated'] or not state['seated']:issues.append('assembly_prerequisite')
   if pr['seal_required'] and not state['seal']:issues.append('seal_before_fastening')
   pos=len(state['sequence'])
   if pos>=4 or a['index']!=pr['sequence'][pos]:issues.append('fastener_sequence')
   if not pr['minimum_effort']<=a['effort']<=pr['maximum_effort']:issues.append('effort_interval')
   state['fasteners'][a['index']]=a['effort'];state['sequence'].append(a['index'])
  elif op=='inspect':state['inspected']=True
  for issue in issues:checks.append({'check':issue,'passed':False,'step':index,'component':'fastener-'+str(a['index']) if op=='fasten' else op})
  trace.append({'index':index,'action':a,'before':before,'after':copy.deepcopy(state),'issues':issues,'passed':not issues})
 final=[('isolated',state['isolated']),('insert_seated',state['seated']),('seal_present',state['seal'] or not pr['seal_required']),
 ('complete_sequence',state['sequence']==pr['sequence']),('all_efforts_in_range',all(pr['minimum_effort']<=x<=pr['maximum_effort'] for x in state['fasteners'])),('final_inspection',state['inspected'])]
 checks.extend({'check':k,'passed':bool(v),'step':len(actions)-1,'component':'assembly'} for k,v in final)
 return {'passed':all(x['passed'] for x in checks),'trace':trace,'checks':checks,'final_state':state,'plan_hash':digest(p),'actions_hash':digest(actions),'model':'Declared logical assembly, dimensionless effort. No physical torque or safety validation.'}

SCENARIOS={
'unchanged':('Same task, different station','The accepted scope still fits. Reuse should be permitted.'),
'documentation':('Harmless documentation edit','Notes changed; the executable work instruction did not.'),
'procedure':('A different fastening order','The new procedure changes the required sequence.'),
'equipment':('A revised fixture','A narrower effort range changes the accepted conditions.'),
'family':('Similar appearance, different family','An accepted fix must not transfer to an unrelated fixture family.'),
'missing':('Observation not available','A missing seal reading cannot be filled in by the assistant.'),
'stale':('Old observation','A previously valid observation is now too old.'),
'permission':('Different access role','The role cannot retrieve the fix. This says nothing about technical truth.'),
'conflict':('Two observations disagree','An expert must resolve the conflict.'),
'record':('Work record changed','The local record is behind the current authoritative revision.'),
'tamper':('Source identity changed','The retained source no longer matches its recorded hash.'),
'revoked':('Review withdrawn','An earlier acceptance no longer authorizes reuse.'),
'absent_seal':('Seal known to be absent','A prerequisite is observably false, rather than unknown.'),
'bad_fix':('Accepted fix, wrong action','Acceptance alone is insufficient: independent execution detects the mistake.'),
}
def scenario(name='unchanged'):
 require(name in SCENARIOS,'unknown scenario');p=default_plan();c=default_context();f=default_fix()
 if name=='documentation':p['documentation_revision']='D2';p['note']='Editorial clarification; executable procedure unchanged.';c['documentation_revision']='D2'
 if name=='procedure':p['revision']='P2';p['procedure']['sequence']=[0,2,3,1];c['procedure_revision']='P2'
 if name=='equipment':p['equipment_revision']='E2';p['procedure']['minimum_effort']=0.25;p['procedure']['maximum_effort']=0.40;c['equipment_revision']='E2'
 if name=='family':p['family']='different-training-fixture';c['family']=p['family']
 if name=='missing':c['observed_seal']=None;c['observation_quality']='MISSING'
 if name=='stale':c['observation_age_seconds']=300
 if name=='permission':c['role']='visitor'
 if name=='conflict':c['evidence_conflict']=True
 if name=='record':c['authoritative_record_revision']='W2'
 if name=='tamper':f['source']['text']='An altered source record.'
 if name=='revoked':f['review']['decision']='REVOKED'
 if name=='absent_seal':c['observed_seal']=False
 if name=='bad_fix':f['actions'][3]['effort']=0.95
 # Deliberately erroneous acceptance, not a post-review content edit. The independent oracle must still fail it.
 if name=='bad_fix':f['reviewed_content_hash']=content_id(f)
 f['event_id']='capture-'+name
 return {'name':name,'title':SCENARIOS[name][0],'description':SCENARIOS[name][1],'fix':f,'context':c,'plan':p,'original_plan':default_plan(),'original_context':default_context()}

def inspect_case(case):
 validate_case(case)
 decision=assess(case)
 if decision['access']=='DENIED':return {'decision':decision,'original':None,'current':None,'case':{'title':case.get('title','Restricted scenario'),'context':{'role':case['context']['role']}}}
 original=None
 if case.get('original_plan') and case.get('original_context'):
  baseline={'fix':copy.deepcopy(case['fix']),'context':case['original_context'],'plan':case['original_plan']}
  original=execute(baseline)
 # Counterfactual execution is quarantined and never authorizes reuse.
 current=execute(case)
 return {'decision':decision,'original':original,'current':current,'case':case,
 'warning':'Right-hand trace is an isolated counterfactual when reuse is blocked. It cannot approve or execute a real task.'}

def propose_update(case):
 validate_case(case);require(assess(case)['access']=='ALLOWED','Access denied; cannot adapt this fix')
 child=copy.deepcopy(case);p=child['plan'];c=child['context'];f=child['fix'];parent=digest(f)
 f['id']=f['id']+'-adapted';f['event_id']='adaptation-'+digest(case)[:12];f['title']='Proposed adaptation to '+p['revision']+' / '+p['equipment_revision']
 f['explanation']='Deterministic proposal derived from the declared current work plan. New review required; no new physical measurement was taken.'
 f['scope'].update(family=p['family'],equipment_revision=p['equipment_revision'],procedure_revision=p['revision'],documentation_revision=p['documentation_revision'],semantic_id=semantic_id(p))
 f['actions']=actions_for(p);f['source']={'id':'PLAN-'+p['id'],'revision':p['revision'],'text':f['explanation'],'parent_fix_hash':parent,'plan_hash':digest(p)};f['source_hash']=digest(f['source']);f.pop('reviewed_content_hash',None)
 f['review']={'decision':'PROPOSED','reviewer':'Not reviewed','role':'trainer','reason':'A generated adaptation cannot approve itself.'}
 child['original_plan']=copy.deepcopy(p);child['original_context']=copy.deepcopy(c);child['parent_case_hash']=digest(case);child['title']=f['title'];child['name']='custom-adaptation'
 return child
