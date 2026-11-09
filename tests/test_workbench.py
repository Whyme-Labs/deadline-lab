from __future__ import annotations
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from deadline_lab.minimize import minimize
from deadline_lab.oracle import evaluate
from deadline_lab.runner import ROOT, Actor, run_scenario
from deadline_lab.scenario import generate, validate
from deadline_lab.trace import TraceWriter, read_trace


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dl-test-')
        self.root = Path(self.temp.name)
        self.count = 0

    def tearDown(self):
        self.temp.cleanup()

    def run_fixture(self, name='cancel', mode='reference'):
        scenario = json.loads((ROOT / 'examples' / (name + '.json')).read_text())
        self.count += 1
        out = self.root / str(self.count)
        return run_scenario(scenario, mode, out), out

    def recheck(self, out):
        data = json.loads((out/'oracle-inputs.json').read_text())
        return evaluate(out/'effects.jsonl', {int(k):v for k,v in data['commands'].items()},
                        {int(k):v for k,v in data['attempts'].items()}, data['probe_id'])

    def test_reference_handles_four_fault_families(self):
        for name in ['expiry','restart','cancel','lost-ack']:
            with self.subTest(name=name):
                result, _ = self.run_fixture(name)
                self.assertEqual('PASS', result['verdict'])
                self.assertEqual(1, result['probe_effects'])

    def test_expiry_mutant_is_detected_after_real_process_pause(self):
        result, out = self.run_fixture('expiry', 'omit_expiry')
        self.assertEqual('FAIL',result['verdict'])
        self.assertIn('authorisation_deadline',result['properties'])
        host = [json.loads(l) for l in (out/'host-events.jsonl').read_text().splitlines()]
        self.assertTrue(any(e.get('response')=='stop_observed_and_resumed' for e in host))

    def test_generation_mutant_after_real_sigkill(self):
        result, out = self.run_fixture('restart', 'omit_epoch')
        self.assertEqual('FAIL',result['verdict'])
        self.assertIn('generation_fence',result['properties'])
        events = [json.loads(l) for l in (out/'host-events.jsonl').read_text().splitlines()]
        killed = [e for e in events if e['kind']=='killed']
        self.assertEqual(-9,killed[0]['returncode'])

    def test_cancel_mutant_detected(self):
        result, _ = self.run_fixture('cancel','omit_cancel')
        self.assertEqual(['cancel_acknowledged'],result['properties'])

    def test_duplicate_mutant_after_lost_ack(self):
        result, out = self.run_fixture('lost-ack','omit_dedupe')
        self.assertEqual(['at_most_once'],result['properties'])
        inputs=json.loads((out/'oracle-inputs.json').read_text())
        self.assertTrue(any(a['response']=='unknown_timeout' for a in inputs['attempts'].values()))
        self.assertEqual(3,result['effects'])

    def test_reject_everything_is_not_a_pass(self):
        result,_=self.run_fixture('cancel','reject_all')
        self.assertEqual('FAIL',result['verdict'])
        self.assertEqual(['healthy_progress'],result['properties'])
        self.assertEqual(0,result['effects'])

    def test_effects_are_recorded_by_another_process(self):
        result,out=self.run_fixture('lost-ack')
        trace=read_trace(out/'effects.jsonl')
        host=[json.loads(l) for l in (out/'host-events.jsonl').read_text().splitlines()]
        self.assertNotEqual(os.getpid(),trace[0]['pid'])
        self.assertTrue(all(e['pid'] != trace[0]['pid'] for e in host if e['kind']=='boot'))
        self.assertEqual(6,trace[-1]['final_state'])

    def test_too_late_cancellation_does_not_retroactively_fail_effect(self):
        scenario={'schema':1,'actions':[
            {'op':'mint','key':'x','ttl_ms':5000,'delta':2}, {'op':'prepare','key':'x'},
            {'op':'commit','key':'x'}, {'op':'cancel','key':'x'}]}
        r=run_scenario(scenario,'reference',self.root/'run')
        self.assertEqual('PASS',r['verdict'])

    def test_missing_trace_is_inconclusive(self):
        _,out=self.run_fixture()
        (out/'effects.jsonl').unlink()
        self.assertEqual('INCONCLUSIVE',self.recheck(out)['verdict'])

    def test_truncated_trace_is_inconclusive(self):
        _,out=self.run_fixture()
        path=out/'effects.jsonl'
        path.write_bytes(path.read_bytes()[:-10])
        self.assertEqual('INCONCLUSIVE',self.recheck(out)['verdict'])

    def test_missing_footer_is_inconclusive(self):
        _,out=self.run_fixture()
        path=out/'effects.jsonl'
        path.write_bytes(b'\n'.join(path.read_bytes().splitlines()[:-1])+b'\n')
        self.assertEqual('INCONCLUSIVE',self.recheck(out)['verdict'])

    def test_reordered_trace_is_inconclusive(self):
        _,out=self.run_fixture('lost-ack')
        path=out/'effects.jsonl'
        lines=path.read_bytes().splitlines()
        lines[1],lines[2]=lines[2],lines[1]
        path.write_bytes(b'\n'.join(lines)+b'\n')
        self.assertEqual('INCONCLUSIVE',self.recheck(out)['verdict'])

    def test_modified_trace_is_inconclusive(self):
        _,out=self.run_fixture('lost-ack')
        path=out/'effects.jsonl'
        path.write_bytes(path.read_bytes().replace(b'"delta":5',b'"delta":6',1))
        self.assertEqual('INCONCLUSIVE',self.recheck(out)['verdict'])

    def test_independent_recheck_matches_verdict(self):
        r,out=self.run_fixture('cancel','omit_cancel')
        other=self.recheck(out)
        self.assertEqual(r['violations'],other['violations'])
        self.assertEqual(r['verdict'],other['verdict'])

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):
            run_scenario({'schema':1,'actions':[]},'unsafe',self.root/'run')

    def test_no_external_pid_action(self):
        with self.assertRaises(ValueError):
            validate({'schema':1,'actions':[{'op':'restart','pid':1}]})

    def test_no_shell_action(self):
        with self.assertRaises(ValueError):
            validate({'schema':1,'actions':[{'op':'shell','command':'true'}]})

    def test_wait_budget_bounded(self):
        with self.assertRaises(ValueError):
            validate({'schema':1,'actions':[{'op':'wait','ms':100}]*16})

    def test_missing_dependency_rejected(self):
        with self.assertRaises(ValueError):
            validate({'schema':1,'actions':[{'op':'commit','key':'absent'}]})

    def test_invalid_numeric_field_rejected(self):
        for value in [True,0,-1,100000]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate({'schema':1,'actions':[{'op':'mint','key':'x','ttl_ms':value,'delta':1}]})

    def test_generator_seed_is_reproducible(self):
        self.assertEqual(generate(120),generate(120))
        self.assertNotEqual(generate(120),generate(121))
        for seed in range(20):
            validate(generate(seed))

    def test_minimizer_reduces_and_preserves_property(self):
        scenario=json.loads((ROOT/'examples/cancel.json').read_text())
        scenario['actions']=[{'op':'wait','ms':1}]+scenario['actions']+[{'op':'wait','ms':1}]
        witness,detail=minimize(scenario,'omit_cancel','cancel_acknowledged',repetitions=2)
        self.assertEqual(4,len(witness['actions']))
        self.assertTrue(detail['deletion_1_minimal'])
        self.assertTrue(detail['final_reproduces'])
        self.assertEqual('PASS',run_scenario(witness,'reference',self.root/'fixed')['verdict'])

    def test_failed_initial_witness_cannot_be_minimized(self):
        with self.assertRaises(RuntimeError):
            minimize({'schema':1,'actions':[]},'reference','at_most_once')

    def test_worker_protocol_malformed_input_and_recovery(self):
        rd,wr=os.pipe()
        actor=Actor(ROOT/'build/dl-worker','reference',1,wr,self.root/'stderr')
        try:
            for payload in ['P -1 1 100 200 1','P 1 1 100 200 1 EXTRA','C -1 1','BOGUS','X '+('x'*900)]:
                self.assertEqual('invalid',actor.request(payload))
            self.assertEqual('ok',actor.request('H'))
        finally:
            actor.close();os.close(rd);os.close(wr)

    def test_secondary_domain_is_labelled_as_same_synthetic_plant(self):
        scenario=json.loads((ROOT/'examples/lost-ack.json').read_text())
        r=run_scenario(scenario,'reference',self.root/'dispense',plant_kind='dispenser')
        self.assertEqual('PASS',r['verdict'])
        self.assertEqual('dispenser',r['plant'])
        self.assertFalse(r['physical_actuator_tested'])

    def test_hash_manifest_covers_raw_evidence(self):
        _,out=self.run_fixture()
        manifest=json.loads((out/'manifest.json').read_text())
        self.assertTrue({'effects.jsonl','host-events.jsonl','oracle-inputs.json','result.json'} <= set(manifest))

if __name__=='__main__':
    unittest.main()
