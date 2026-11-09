import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from deadline_lab.adapters.nginx_dav import run, validate, evaluate, REQUIRED
from deadline_lab.evidence import seal
from deadline_lab.external import scenario, run_regressions
from deadline_lab.reducer import reduce_actions


class ExternalValidationTests(unittest.TestCase):
    def test_unknown_fields_and_op_rejected(self):
        s = scenario(5, 'expiry')
        for action in [{'op':'shell','command':'true'}, {'op':'wait','ms':True},
                       {'op':'release','key':[]}, {'op':'wait','ms':-1}]:
            broken = {**s, 'actions':[action]}
            with self.assertRaises(ValueError): validate(broken)

    def test_reserved_keys_rejected(self):
        s = {'schema':2,'adapter':'nginx-dav','actions':[
             {'op':'write','key':'healthy_probe','value':1,'ttl_ms':100}]}
        with self.assertRaises(ValueError): validate(s)

    def test_ambiguous_values_and_unreleased_holds_rejected(self):
        s = scenario(5,'reordering')
        s['actions'][3]['value'] = s['actions'][0]['value']
        with self.assertRaises(ValueError): validate(s)
        s = scenario(5,'reordering'); s['actions'] = s['actions'][:-2]
        with self.assertRaises(ValueError): validate(s)

    def test_empty_scenario_valid_for_healthy_control(self):
        validate({'schema':2,'adapter':'nginx-dav','actions':[]})

    def test_manifest_traversal_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'manifest.json').write_text(json.dumps({'schema':2,'files':{'../escape':'x'}}))
            self.assertEqual('INCONCLUSIVE',evaluate(p)['verdict'])


@unittest.skipUnless(shutil.which('nginx'), 'external target not installed; no external execution')
class ExternalExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_actual_file_changes_after_client_timeout(self):
        s=scenario(5,'expiry')
        r=run(s,'timeout_only',self.root/'bad')
        self.assertEqual('FAIL',r['verdict'])
        self.assertIn('expired_dispatch_effect',r['properties'])
        self.assertIn('superseded_effect',r['properties'])
        self.assertEqual(1,r['timeout_but_effect_observed'])
        self.assertFalse(r['qnx_executed'])
        good=run(s,'fenced',self.root/'good')
        self.assertEqual('PASS',good['verdict'])
        self.assertEqual(1,good['healthy_effects'])

    def test_expiry_guard_does_not_solve_valid_reordering(self):
        s=scenario(5,'reordering')
        r=run(s,'deadline',self.root/'bad')
        self.assertEqual(['superseded_effect'],r['properties'])
        good=run(s,'fenced',self.root/'good')
        self.assertEqual('PASS',good['verdict'])

    def test_lost_ack_is_unknown_not_rollback(self):
        s={'schema':2,'adapter':'nginx-dav','actions':[
            {'op':'lost_ack','key':'x','value':33,'ttl_ms':100}]}
        r=run(s,'fenced',self.root/'run')
        self.assertEqual('PASS',r['verdict'])
        self.assertEqual(1,r['timeout_but_effect_observed'])
        self.assertEqual(1,r['observed_file_effects'])

    def test_reject_all_fails_liveness(self):
        r=run({'schema':2,'adapter':'nginx-dav','actions':[]},'reject_all',self.root/'run')
        self.assertEqual(['healthy_progress'],r['properties'])

    def test_missing_and_modified_evidence_is_inconclusive(self):
        p=self.root/'run'; r=run(scenario(9,'reordering'),'fenced',p)
        self.assertEqual('PASS',r['verdict'])
        original=(p/'history.json').read_bytes()
        (p/'history.json').write_bytes(original+b' ')
        self.assertEqual('INCONCLUSIVE',evaluate(p)['verdict'])
        (p/'history.json').write_bytes(original)
        (p/'nginx.conf').unlink()
        self.assertEqual('INCONCLUSIVE',evaluate(p)['verdict'])

    def test_reordered_resealed_observations_are_rejected(self):
        p=self.root/'run'; run(scenario(9,'reordering'),'fenced',p)
        h=json.loads((p/'history.json').read_text()); h[0],h[1]=h[1],h[0]
        (p/'history.json').write_text(json.dumps(h)); seal(p,sorted(REQUIRED))
        self.assertEqual('INCONCLUSIVE',evaluate(p)['verdict'])

    def test_changed_request_identity_is_not_a_pass(self):
        p=self.root/'run'; run(scenario(9,'reordering'),'fenced',p)
        h=json.loads((p/'history.json').read_text()); h[0]['request']['value']+=1
        (p/'history.json').write_text(json.dumps(h)); seal(p,sorted(REQUIRED))
        self.assertEqual('INCONCLUSIVE',evaluate(p)['verdict'])

    def test_unclean_target_exit_is_inconclusive(self):
        p=self.root/'run'; run(scenario(9,'reordering'),'fenced',p)
        m=json.loads((p/'target.json').read_text()); m['target_exit']=-9
        (p/'target.json').write_text(json.dumps(m)); seal(p,sorted(REQUIRED))
        self.assertEqual('INCONCLUSIVE',evaluate(p)['verdict'])

    def test_exported_suite_detects_candidate_regression(self):
        s=scenario(5,'reordering'); suite_dir=self.root/'suite';suite_dir.mkdir()
        (suite_dir/'case.json').write_text(json.dumps(s))
        suite={'schema':2,'adapter':'nginx-dav','cases':[{
            'name':'reorder','scenario':'case.json','property':'superseded_effect',
            'sensitivity_policy':'deadline'}]}
        p=suite_dir/'suite.json';p.write_text(json.dumps(suite))
        good=run_regressions(p,self.root/'good',sensitivity=True)
        self.assertTrue(good['passed']); self.assertEqual(2,good['checks'])
        bad=run_regressions(p,self.root/'bad',candidate='deadline')
        self.assertFalse(bad['passed'])
        self.assertIn('<failure',(self.root/'bad/junit.xml').read_text())


class AdapterReducerTests(unittest.TestCase):
    @staticmethod
    def validator(s):
        if 'actions' not in s: raise ValueError('missing actions')
    def test_adapter_independent_reduction(self):
        def runner(s,p):
            p.mkdir()
            broken=any(a.get('op')=='trigger' for a in s['actions'])
            return {'verdict':'FAIL' if broken else 'PASS','properties':['p'] if broken else []}
        witness,record=reduce_actions({'actions':[{'op':'noise'},{'op':'trigger'},{'op':'noise'}]},
                                     runner,self.validator,'p')
        self.assertEqual([{'op':'trigger'}],witness['actions'])
        self.assertTrue(record['deletion_1_minimal'])
    def test_inconclusive_cannot_be_failure_witness(self):
        with self.assertRaises(RuntimeError):
            reduce_actions({'actions':[{}]},lambda s,p:{'verdict':'INCONCLUSIVE','properties':['p']},
                           self.validator,'p')
    def test_execution_budget_fail_closed(self):
        with self.assertRaises(RuntimeError):
            reduce_actions({'actions':[{},{}]},lambda s,p:{'verdict':'FAIL','properties':['p']},
                           self.validator,'p',max_executions=2)
