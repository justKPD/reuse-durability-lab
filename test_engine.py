import unittest,copy,tempfile,json
from pathlib import Path
from engine import *
from storage import Store
from experiments import campaign

class EngineTests(unittest.TestCase):
 def test_json_equivalent_numbers_keep_evidence_identity(self):self.assertEqual(digest({'state':[0.0,1.0,.55]}),digest({'state':[0,1,.55]}))
 def test_all_presets_are_valid(self):
  for n in SCENARIOS:validate_case(scenario(n))
 def test_expected_decisions(self):
  expected={'unchanged':'ALLOWED','documentation':'ALLOWED','procedure':'REVIEW_REQUIRED','equipment':'REVIEW_REQUIRED','family':'INAPPLICABLE','missing':'INSUFFICIENT_EVIDENCE','stale':'INSUFFICIENT_EVIDENCE','permission':'ACCESS_DENIED','conflict':'REVIEW_REQUIRED','record':'REVIEW_REQUIRED','tamper':'INSUFFICIENT_EVIDENCE','revoked':'REVIEW_REQUIRED','absent_seal':'INAPPLICABLE','bad_fix':'ALLOWED'}
  for n,status in expected.items():
   with self.subTest(n=n):self.assertEqual(assess(scenario(n))['status'],status)
 def test_original_executes_and_order_is_recorded(self):
  r=execute(scenario());self.assertTrue(r['passed']);self.assertEqual(r['final_state']['sequence'],[0,2,1,3]);self.assertEqual(len(r['trace']),8)
 def test_changed_plan_cannot_rewrite_oracle(self):
  c=scenario('procedure');r=execute(c);self.assertFalse(r['passed']);self.assertTrue(any(x['check']=='fastener_sequence' for x in r['checks']))
 def test_changed_effort_detected_by_oracle(self):self.assertFalse(execute(scenario('equipment'))['passed'])
 def test_bad_accepted_fix_keeps_failure(self):
  c=scenario('bad_fix');self.assertTrue(assess(c)['can_execute']);self.assertFalse(execute(c)['passed']);self.assertFalse(inspect_case(c)['original']['passed'])
 def test_permission_is_separate_from_technical_truth(self):
  r=inspect_case(scenario('permission'));self.assertIsNone(r['decision']['technical_status']);self.assertIsNone(r['current']);self.assertNotIn('fix',r['case'])
 def test_missing_and_false_observation_are_different(self):
  self.assertEqual(assess(scenario('missing'))['status'],'INSUFFICIENT_EVIDENCE');self.assertEqual(assess(scenario('absent_seal'))['status'],'INAPPLICABLE')
 def test_harmless_revision_strict_baseline_is_conservative(self):
  c=scenario('documentation');self.assertEqual(assess(c,'exact_revision')['status'],'REVIEW_REQUIRED');self.assertEqual(assess(c)['status'],'ALLOWED')
 def test_arbitrary_custom_parameters_are_executed(self):
  c=scenario();c['plan']['procedure']['minimum_effort']=.1;c['plan']['procedure']['maximum_effort']=.2
  self.assertFalse(execute(c)['passed']);c['fix']['actions']=actions_for(c['plan']);self.assertTrue(execute(c)['passed'])
 def test_invalid_numbers_rejected(self):
  for value in [float('nan'),float('inf'),True,-1]:
   c=scenario();c['context']['observation_age_seconds']=value
   with self.assertRaises(ValueError):assess(c)
 def test_inconsistent_context_and_authority_rejected(self):
  c=scenario();c['context']['procedure_revision']='FAKE'
  with self.assertRaises(ValueError):assess(c)
 def test_custom_case_does_not_invent_original_reference(self):
  c=scenario();del c['original_plan'];del c['original_context'];self.assertIsNone(inspect_case(c)['original'])
 def test_missing_fields_fail_closed(self):
  c=scenario();del c['fix']['scope']['allowed_roles']
  with self.assertRaises(ValueError):assess(c)
 def test_changed_fix_content_requires_new_review(self):
  c=scenario();c['fix']['actions'][3]['effort']=.6;self.assertEqual(assess(c)['status'],'REVIEW_REQUIRED')
 def test_adaptation_is_proposed_and_references_parent(self):
  c=propose_update(scenario('procedure'));self.assertEqual(c['fix']['review']['decision'],'PROPOSED');self.assertTrue(execute(c)['passed']);self.assertIn('parent_case_hash',c)
 def test_duplicate_fastening_is_not_success(self):
  c=scenario();c['fix']['actions'].insert(4,{'op':'fasten','index':0,'effort':.55});self.assertFalse(execute(c)['passed'])

class StoreTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'records.sqlite3')
 def tearDown(self):self.tmp.cleanup()
 def test_idempotency_and_conflict(self):
  c=scenario();self.assertFalse(self.store.capture(c)['duplicate']);self.assertTrue(self.store.capture(c)['duplicate']);c['fix']['title']='Changed'
  with self.assertRaises(ValueError):self.store.capture(c)
 def test_review_requires_explicit_authority_and_reason(self):
  with self.assertRaises(ValueError):self.store.review(scenario(),'ACCEPTED','Demo','valid reason','operator')
  with self.assertRaises(ValueError):self.store.review(scenario(),'ACCEPTED','Demo','ok','trainer')
 def test_invalid_original_cannot_be_accepted(self):
  with self.assertRaises(ValueError):self.store.review(scenario('bad_fix'),'ACCEPTED','Demo','Reference check examined','trainer')
 def test_review_revocation_changes_reuse(self):
  c=self.store.review(scenario(),'REVOKED','Demo','New evidence needs review','trainer');self.assertEqual(assess(c)['status'],'REVIEW_REQUIRED')
 def test_restart_and_ledger(self):
  c=self.store.save_run(inspect_case(scenario()));other=Store(self.store.path);self.assertEqual(other.load(c['id']),c);self.assertTrue(other.audit()['valid'])
 def test_revocation_overrides_old_client_snapshot(self):
  old=scenario();self.store.review(old,'REVOKED','Demo','Evidence now needs review','trainer');self.assertEqual(assess(self.store.resolve_review(old))['status'],'REVIEW_REQUIRED')
 def test_changed_fix_cannot_borrow_persisted_acceptance(self):
  old=scenario();self.store.review(old,'ACCEPTED','Demo','Reference evidence checked','trainer');old['fix']['actions'][3]['effort']=.6;self.assertEqual(self.store.resolve_review(old)['fix']['review']['decision'],'PROPOSED')
 def test_proposed_adaptation_can_be_explicitly_reviewed(self):
  c=propose_update(scenario('procedure'));c=self.store.review(c,'ACCEPTED','Demo','Current declared work plan verified','trainer');self.assertTrue(assess(c)['can_execute']);self.assertTrue(execute(c)['passed'])
 def test_missing_observation_cannot_be_approved_away(self):
  c=propose_update(scenario('missing'))
  with self.assertRaises(ValueError):self.store.review(c,'ACCEPTED','Demo','Attempted approval without observation','trainer')
 def test_tampering_is_detected(self):
  self.store.capture(scenario())
  with self.store.connect() as db:db.execute("UPDATE ledger SET payload='{}'")
  self.assertFalse(self.store.audit()['valid'])

class ExperimentTests(unittest.TestCase):
 def test_same_seed_same_cases_and_outcomes(self):
  a=campaign(4,28,2);b=campaign(4,28,2);self.assertEqual(a['trials'],b['trials'])
 def test_review_budget_is_enforced(self):
  for r in campaign(9,140,1)['results']:self.assertLessEqual(r['review_performed'],1)
 def test_negative_result_is_not_hidden(self):
  r=campaign(42,140,20)['results'][-1];self.assertGreater(r['execution_failures'],0);self.assertGreater(r['unresolved'],0)
 def test_all_four_policies_share_cases(self):
  r=campaign(8,28,0)['trials'];sets=[{x['case_hash'] for x in r if x['policy']==p} for p in POLICIES];self.assertTrue(all(s==sets[0] for s in sets))

if __name__=='__main__':unittest.main(verbosity=2)
