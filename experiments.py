"""Seeded synthetic comparison. No hidden LLM calls or claims of measured human time."""
import random,copy,time,json,statistics
from engine import scenario,SCENARIOS,POLICIES,assess,execute,semantic_id,digest,require

def ground_truth(case):
 """Independently specified eligible-reuse conditions, separate from policy dispatch."""
 f,c,p=case['fix'],case['context'],case['plan'];s=f['scope']
 if c['role'] not in s['allowed_roles']:return None
 return (f['review']['decision']=='ACCEPTED' and c['family']==s['family'] and semantic_id(p)==s['semantic_id']
  and digest(f['source'])==f['source_hash'] and c['source_available'] and not c['evidence_conflict']
  and c['work_record_revision']==c['authoritative_record_revision'] and c['observation_quality']=='GOOD'
  and c['observation_age_seconds']<=s['maximum_observation_age_seconds'] and (not p['procedure']['seal_required'] or c['observed_seal'] is True))

def campaign(seed=42,count=140,review_budget=20):
 require(type(seed)==int and 0<=seed<=1000000,'seed out of range');require(type(count)==int and 14<=count<=1400,'count must be 14 to 1400');require(type(review_budget)==int and 0<=review_budget<=1400,'review budget out of range')
 rng=random.Random(seed);names=list(SCENARIOS);cases=[]
 # A fixed coverage round plus a random mixture. Randomize task parameters, not only scenario names.
 for i in range(count):
  name=names[i] if i<len(names) else rng.choice(names);case=scenario(name)
  case['context']['task_id']=f'trial-{seed}-{i}';case['fix']['event_id']=f'event-{seed}-{i}'
  case['context']['station']=f'Station {rng.randint(1,6)}'
  if name=='stale':case['context']['observation_age_seconds']=rng.randint(121,1000)
  elif name!='missing':case['context']['observation_age_seconds']=rng.randint(0,110)
  if name=='documentation':case['plan']['documentation_revision']=f'D{rng.randint(2,20)}';case['context']['documentation_revision']=case['plan']['documentation_revision']
  cases.append(case)
 rows=[];trials=[]
 for policy in POLICIES:
  stats=dict(policy=policy,total=count,access_denied=0,allowed=0,false_reuse=0,eligible=0,eligible_reused=0,valid_tasks_completed=0,unnecessary_review=0,review_requested=0,review_performed=0,review_budget=review_budget,review_units=0,unresolved=0,execution_failures=0,executed=0)
  durations=[]
  for case in cases:
   t=time.perf_counter();d=assess(case,policy);durations.append((time.perf_counter()-t)*1000);truth=ground_truth(case)
   outcome=None;reviewed=False
   if truth is None:stats['access_denied']+=1
   else:
    if truth:stats['eligible']+=1
    if d['status']=='ALLOWED':
     stats['allowed']+=1
     if not truth:stats['false_reuse']+=1
     else:stats['eligible_reused']+=1
     outcome=execute(case);stats['executed']+=1;stats['execution_failures']+=not outcome['passed'];stats['valid_tasks_completed']+=bool(truth and outcome['passed'])
    elif d['status']=='REVIEW_REQUIRED':
     stats['review_requested']+=1;stats['unnecessary_review']+=bool(truth)
     if stats['review_performed']<review_budget:
      stats['review_performed']+=1;stats['review_units']+=1;reviewed=True
      # Synthetic review can identify validity; it does not manufacture missing observations or new repairs.
     else:stats['unresolved']+=1
    elif d['status']=='INSUFFICIENT_EVIDENCE':stats['unresolved']+=1
   trials.append({'policy':policy,'task_id':case['context']['task_id'],'scenario':case['name'],'decision':d['status'],'eligible_under_declared_contract':truth,'review_performed':reviewed,'execution_passed':None if outcome is None else outcome['passed'],'case_hash':digest(case)})
  stats['reuse_coverage']=stats['eligible_reused']/stats['eligible'] if stats['eligible'] else None
  stats['median_decision_ms']=round(statistics.median(durations),4);rows.append(stats)
 return {'seed':seed,'count':count,'review_budget_per_policy':review_budget,'results':rows,'trials':trials,
 'cost_model':'One synthetic expert review = one assumed review unit. Not measured minutes, euros, or human effort. Policy CPU latency is measured locally and does not include network/LLM time.',
 'limitations':['Synthetic scenario distribution; not plant data or a user study.','False reuse means violating the declared applicability/evidence contract, NOT all incorrect physical actions. Execution failures are reported separately.','The full gate encodes these known contract checks, so zero contract violations on this fixture is a conformance result by construction, not empirical proof of superiority on unknown industrial data.','accepted_only is an accepted-record retrieval baseline, not a measured production RAG or LLM system.','semantic_rules and durability_gate share a simple semantic rule. Added checks must justify their integration cost.','An accepted but wrongly authored fix can pass the reuse gate and still fail independent execution. That negative control is deliberately retained.','No evidence that an agent council improves these deterministic checks.'],
 'implementation': 'Policy and oracle code are separate, but both implement this same authored fixture specification; they are not an external industrial oracle.'}

if __name__=='__main__':
 import argparse,pathlib
 p=argparse.ArgumentParser();p.add_argument('--seed',type=int,default=42);p.add_argument('--count',type=int,default=140);p.add_argument('--output',default='results/campaign.json');a=p.parse_args()
 out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);res=campaign(a.seed,a.count);out.write_text(json.dumps(res,indent=2),encoding='utf-8');print(json.dumps(res['results'],indent=2))
