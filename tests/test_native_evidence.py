"""Pure offline checker tests. Every fixture is labelled synthetic-unit-test."""
import errno
import json
import platform
import tempfile
import unittest
from pathlib import Path
from deadline_lab.adapters import qnx_native as q
from deadline_lab.evidence import seal
from deadline_lab.trace import TraceWriter


def fixture(root: Path, broken=False, healthy=True):
    root.mkdir()
    (root/'scenario.json').write_text(json.dumps(q.DEFAULT_SCENARIO))
    (root/'target.json').write_text(json.dumps({'evidence_origin':'synthetic-unit-test',
        'timeout_errnos':[errno.ETIMEDOUT,errno.ECANCELED]}))
    (root/'completion.json').write_text(json.dumps({'complete':True,'error':None,
                                                  'server_exit':0,'observer_exit':0}))
    clients=[{'id':1,'epoch':1,'status':0 if broken else -1,'errno':0 if broken else errno.ETIMEDOUT,
        'issued_ns':90,'expires_ns':1000000,'reply_result':1 if broken else 0,
        'reply_version':1 if broken else 0,'reply_id':1 if broken else 0},
        {'id':2,'epoch':1,'status':0 if healthy else -1,'errno':0 if healthy else errno.EINVAL,
        'issued_ns':190,'expires_ns':1000000,'reply_result':1 if healthy else 0,
        'reply_version':1,'reply_id':2}]
    (root/'clients.json').write_text(json.dumps(clients))
    events=[{'kind':'start','id':0,'monotonic_ns':1},
            {'kind':'received','id':1,'monotonic_ns':100},
            {'kind':'unblock_observed','id':1,'monotonic_ns':150}]
    events.append({'kind':'effect' if broken else 'cancel_ack','id':1,'monotonic_ns':170})
    events.append({'kind':'received','id':2,'monotonic_ns':200})
    if healthy: events.append({'kind':'effect','id':2,'monotonic_ns':210})
    events.append({'kind':'end','id':0,'monotonic_ns':220})
    (root/'server.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    trace=TraceWriter(root/'effects.jsonl');trace.write('start',monotonic_ns=1,plant='synthetic-test')
    state=0
    for cid,stamp in ([(1,170)] if broken else [])+([(2,210)] if healthy else []):
        trace.write('effect',command_id=cid,attempt=cid,request_epoch=1,worker_epoch=1,
                    commit_ns=stamp,observed_ns=stamp+1,delta=1,state_before=state,state_after=state+1)
        state+=1
    trace.write('end',complete=True,effect_count=state,final_state=state,monotonic_ns=221)
    trace.close()
    for name in ('server.stderr','observer.stderr'): (root/name).write_text('')
    seal(root,sorted(q.REQUIRED))
    return root


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def reseal(self,p): seal(p,sorted(q.REQUIRED))
    def test_reference_offline_fixture(self):
        r=q.evaluate(fixture(self.root/'a'))
        self.assertEqual('PASS',r['verdict']);self.assertEqual(1,r['unblock_activations'])
        self.assertFalse(r['qnx_executed'])
    def test_effect_after_unblock_detected(self):
        r=q.evaluate(fixture(self.root/'a',broken=True))
        self.assertEqual('FAIL',r['verdict']);self.assertIn('cancel_before_effect',r['properties'])
        self.assertFalse(r['qnx_executed'])
    def test_missing_healthy_progress_detected(self):
        r=q.evaluate(fixture(self.root/'a',healthy=False))
        self.assertEqual('FAIL',r['verdict']);self.assertIn('healthy_progress',r['properties'])
    def test_no_fault_activation_is_inconclusive(self):
        p=fixture(self.root/'a')
        events=[json.loads(s) for s in (p/'server.jsonl').read_text().splitlines()]
        (p/'server.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events if e['kind']!='unblock_observed'))
        self.reseal(p)
        self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_modified_observer_trace_is_inconclusive(self):
        p=fixture(self.root/'a');f=p/'effects.jsonl';f.write_bytes(f.read_bytes().replace(b'"delta":1',b'"delta":2'))
        self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_resealed_but_broken_trace_chain_rejected(self):
        p=fixture(self.root/'a');f=p/'effects.jsonl';f.write_bytes(f.read_bytes().replace(b'"delta":1',b'"delta":2'))
        self.reseal(p);self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_no_end_event_rejected(self):
        p=fixture(self.root/'a');f=p/'server.jsonl';f.write_text('\n'.join(f.read_text().splitlines()[:-1])+'\n')
        self.reseal(p);self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_server_log_cannot_invent_an_observed_effect(self):
        p=fixture(self.root/'a');f=p/'server.jsonl'
        e=[json.loads(x) for x in f.read_text().splitlines()]
        e.insert(-1,{'kind':'effect','id':1,'monotonic_ns':219})
        f.write_text(''.join(json.dumps(x)+'\n' for x in e));self.reseal(p)
        self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_reply_identity_checked(self):
        p=fixture(self.root/'a');f=p/'clients.json';c=json.loads(f.read_text());c[-1]['reply_id']=999
        f.write_text(json.dumps(c));self.reseal(p)
        self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_unclean_exit_cannot_pass(self):
        p=fixture(self.root/'a');f=p/'completion.json';c=json.loads(f.read_text());c['server_exit']=-9
        f.write_text(json.dumps(c));self.reseal(p)
        self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_missing_client_is_inconclusive(self):
        p=fixture(self.root/'a');f=p/'clients.json';f.write_text(json.dumps(json.loads(f.read_text())[:-1]))
        self.reseal(p);self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_unknown_origin_rejected(self):
        p=fixture(self.root/'a');f=p/'target.json';t=json.loads(f.read_text());t['evidence_origin']='claimed-qnx'
        f.write_text(json.dumps(t));self.reseal(p)
        self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_invalid_native_scenario_rejected(self):
        for actions in ([],[{'op':'call','work_ms':1,'timeout_ms':10,'expect_unblock':False}],
                       [{'op':'shell','work_ms':1,'timeout_ms':10,'expect_unblock':True}]):
            with self.assertRaises(ValueError): q.validate({**q.DEFAULT_SCENARIO,'actions':actions})
    @unittest.skipIf(platform.system()=='QNX','local non-QNX guard test only')
    def test_linux_does_not_masquerade_as_qnx(self):
        r=q.run(q.DEFAULT_SCENARIO,'reference',self.root/'guard',self.root/'not-binaries')
        self.assertEqual('NOT_RUN',r['verdict']);self.assertFalse(r['qnx_executed'])
