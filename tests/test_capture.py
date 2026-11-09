"""Real POSIX capture tests; NONE is QNX compilation or native API emulation."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from deadline_lab import capture
from deadline_lab.adapters import qnx_native
from deadline_lab import native_workflow

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.environ.get('DL_CAPTURE_TEST_BIN', str(ROOT / 'build'))).resolve()
TOKEN = 'cafebabecafebabecafebabecafebabe'
BUDGET_SCALE = int(os.environ.get('DL_CAPTURE_BUDGET_SCALE', '1'))
if not 1 <= BUDGET_SCALE <= 10:
    raise ValueError('test budget scale must be 1..10')
SCENARIO = qnx_native.DEFAULT_SCENARIO


def frame(files):
    return b'DLCAP1\n' + b''.join(b'FILE ' + n.encode() + b' ' + str(len(b)).encode() + b'\n' + b + b'\n'
                                for n, b in files.items()) + b'END\n'


class StreamTests(unittest.TestCase):
    def test_exact_roundtrip(self):
        files = {'capture.json': b'{"status":"NOT_RUN"}\n', 'server.stderr': b'\x00not text\xff'}
        self.assertEqual(files, capture.decode_stream(frame(files)))

    def test_empty_file(self):
        self.assertEqual(b'', capture.decode_stream(frame({'capture.json': b'', 'server.stderr': b''}))['server.stderr'])

    def test_all_truncations_rejected(self):
        data = frame({'capture.json': b'{"token":"example"}\n'})
        for size in range(len(data)):
            with self.subTest(size=size), self.assertRaises(ValueError):
                capture.decode_stream(data[:size])

    def test_unsafe_or_unknown_paths_rejected(self):
        for name in ('../outside', '/absolute', '.', 'clients/1.stdout', 'source-history.bundle', 'client-10.stdout'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                capture.decode_stream(frame({name: b'{}', 'capture.json': b'{}'}))

    def test_duplicate_frame_rejected(self):
        item = b'FILE capture.json 2\n{}\n'
        with self.assertRaises(ValueError):
            capture.decode_stream(b'DLCAP1\n' + item + item + b'END\n')

    def test_bad_lengths_and_suffix(self):
        for size in (b'-1', b'999999', b'0002', b'1e2'):
            with self.subTest(size=size), self.assertRaises(ValueError):
                capture.decode_stream(b'DLCAP1\nFILE capture.json ' + size + b'\n{}\nEND\n')
        with self.assertRaises(ValueError):
            capture.decode_stream(frame({'capture.json': b'{}'}) + b'extra')

    def test_stream_bound(self):
        with self.assertRaises(ValueError):
            capture.decode_stream(b'DLCAP1\n' + b'a' * capture.MAX_STREAM)

    def test_duplicate_json_and_nan(self):
        for raw in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError): capture.loads(raw)


class RawObservationTests(unittest.TestCase):
    def raw(self):
        return b'\n'.join(json.dumps(row).encode() for row in [
            {'kind':'start','pid':1,'monotonic_ns':10},
            {'kind':'effect','observed_ns':30,'wire':'E 1 1 1 1 20 1\n'},
            {'kind':'end','complete':True,'effect_count':1,'monotonic_ns':40}]) + b'\n'

    def test_normalize_uses_target_clock(self):
        rows = capture.normalized_effects(self.raw())
        self.assertEqual(30, rows[1]['observed_ns'])
        self.assertEqual(1, rows[-1]['final_state'])

    def test_future_commit_rejected(self):
        with self.assertRaises(ValueError): capture.normalized_effects(self.raw().replace(b'1 20 1', b'1 35 1'))

    def test_partial_effect_or_observer_rejected(self):
        with self.assertRaises(ValueError): capture.normalized_effects(self.raw()[:-1])
        with self.assertRaises(ValueError): capture.normalized_effects(self.raw().replace(b'\\n"}', b'"}'))

    def test_noncanonical_or_overflow_wire(self):
        for replacement in ('E 0 1 1 1 20 1\n', 'E 1 1 1 1 20 0\n', 'E 1 1 1 1 20 1000001\n',
                            'E 18446744073709551616 1 1 1 20 1\n'):
            data = self.raw().replace(json.dumps('E 1 1 1 1 20 1\n').encode(), json.dumps(replacement).encode())
            with self.subTest(replacement=replacement), self.assertRaises(ValueError): capture.normalized_effects(data)

    def test_incomplete_raw_completion_rejected(self):
        with self.assertRaises(ValueError): capture.normalized_effects(self.raw().replace(b'true', b'false'))


class CommandTests(unittest.TestCase):
    def test_ssh_keeps_host_key_verification_and_quotes_target_path(self):
        directory = "/tmp/qnx binaries ' quoted"
        cmd = capture.capture_command(directory, 'reference', SCENARIO, TOKEN, ssh='user@qnx-test')
        self.assertIn('-oStrictHostKeyChecking=yes', cmd)
        self.assertIn('-oBatchMode=yes', cmd)
        import shlex
        remote = shlex.split(cmd[-1])
        self.assertEqual(directory + '/dl-capture', remote[0])
        self.assertEqual(directory, remote[remote.index('--bin') + 1])

    def test_ssh_options_cannot_be_injected(self):
        for host in ('-oProxyCommand=bad', 'user@host;echo', 'a\nssh', 'host x', ''):
            with self.subTest(host=host), self.assertRaises(ValueError):
                capture.capture_command('/tmp/bin', 'reference', SCENARIO, TOKEN, ssh=host)

    def test_invalid_token_and_binary_path(self):
        with self.assertRaises(ValueError): capture.capture_command('relative', 'reference', SCENARIO, TOKEN)
        with self.assertRaises(ValueError): capture.capture_command('/tmp/b', 'reference', SCENARIO, '../bad')

    def test_test_fixture_cannot_be_dispatched_remotely(self):
        with self.assertRaises(ValueError): capture.capture_command('/tmp/b','normal',SCENARIO,TOKEN,fixture=True,ssh='host')


@unittest.skipUnless((BIN / 'dl-capture').exists(), 'compile portable C collector first')
class RealCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='dl-capture-tests-')
        self.root = Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()

    def collect(self, mode='normal', scenario=SCENARIO, budget=1200):
        cmd = capture.capture_command(str(BIN), mode, scenario, TOKEN, fixture=True, budget_ms=budget * BUDGET_SCALE)
        # No interpreter, sha256 command, shell or other PATH dependency on target.
        env = {**os.environ, 'PATH': '/definitely-no-interpreter', 'TMPDIR': str(self.root)}
        r = capture.execute(cmd, timeout=max(6, budget * BUDGET_SCALE / 1000 + 5), env=env)
        files = capture.decode_stream(r['stdout'])
        cap = capture.loads(files['capture.json'])
        diagnostics = r['stderr'] + b'\n'.join(v for k, v in files.items() if k.endswith('.stderr'))
        self.assertNotIn(b'ERROR: AddressSanitizer', diagnostics)
        self.assertNotIn(b'runtime error:', diagnostics)
        for call in cap['calls']:
            if call['pid']:
                with self.assertRaises(ProcessLookupError): os.kill(call['pid'], 0)
        if cap['server_pid']:
            with self.assertRaises(ProcessLookupError): os.kill(cap['server_pid'], 0)
        self.assertEqual([], list(self.root.iterdir()), 'streaming collector must remove only its own scratch tree')
        return r, files, cap

    def test_complete_without_python_or_shell_on_target_path(self):
        r, files, cap = self.collect()
        self.assertEqual(0, r['exit'])
        self.assertEqual('COMPLETE', cap['status'])
        self.assertEqual('posix-capture-test', cap['evidence_origin'])
        self.assertFalse(cap['qnx_executed'])
        self.assertEqual(1, capture.normalized_effects(files['effects.raw.jsonl'])[-1]['effect_count'])
        with self.assertRaises(ValueError): capture.native_material(files, {'scenario':SCENARIO,'token':TOKEN,'mode':'normal'})

    def test_runtime_binary_hashes_match_hashlib(self):
        _, files, _ = self.collect()
        ids = capture.loads(files['binaries.json'])['binaries']
        for role in ('server','client','abi','capture'):
            name = 'dl-capture' if role=='capture' else 'dl-transport-' + role
            data = (BIN/name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), ids[role]['sha256'])
            self.assertEqual(len(data), ids[role]['bytes'])
            self.assertTrue(ids[role]['stable'])

    def test_partial_greeting_times_out_and_reaps_server(self):
        r, _, cap = self.collect('partial', budget=250)
        self.assertEqual(78, r['exit'])
        self.assertEqual('INCOMPLETE', cap['status'])
        self.assertTrue(cap['server_reaped'])
        self.assertLess(r['elapsed_seconds'], 2 * BUDGET_SCALE)

    def test_stdout_and_stderr_flood_is_bounded(self):
        r, _, cap = self.collect('flood')
        self.assertEqual(78, r['exit'])
        self.assertIn('bound', cap['error'])

    def test_stderr_and_effect_bursts_do_not_deadlock(self):
        r, files, _ = self.collect('stderr_burst')
        self.assertEqual(0, r['exit']); self.assertEqual(48000, len(files['server.stderr']))
        r, files, _ = self.collect('burst')
        self.assertEqual(0, r['exit'])
        self.assertEqual(100, capture.normalized_effects(files['effects.raw.jsonl'])[-1]['effect_count'])

    def test_invalid_effect_streams_fail_closed(self):
        for mode in ('partial_effect','bad_effect','oversize_effect','many_effects'):
            with self.subTest(mode=mode):
                r, _, cap = self.collect(mode)
                self.assertEqual(78, r['exit'])
                self.assertEqual('INCOMPLETE', cap['status'])

    def test_wrong_greeting_or_early_exit(self):
        for mode in ('wrong_pid','crash'):
            with self.subTest(mode=mode):
                r, _, cap = self.collect(mode)
                self.assertEqual(78, r['exit']); self.assertNotEqual('COMPLETE', cap['status'])

    def test_stubborn_server_is_killed_and_marked_incomplete(self):
        r, _, cap = self.collect('stubborn', budget=300)
        self.assertEqual(78,r['exit']);self.assertEqual(-signal.SIGKILL,cap['server_exit'])
        self.assertTrue(cap['server_reaped'])

    def test_client_failures_do_not_pass(self):
        for work in (996,997,998):
            scenario = {**SCENARIO, 'actions':[dict(SCENARIO['actions'][0], work_ms=work)]}
            with self.subTest(work=work):
                r, _, cap = self.collect(scenario=scenario,budget=350)
                self.assertEqual(78,r['exit']);self.assertEqual('INCOMPLETE',cap['status'])

    def test_linux_default_is_not_native(self):
        cmd = capture.capture_command(str(BIN),'reference',SCENARIO,TOKEN)
        r = capture.execute(cmd, timeout=3)
        self.assertEqual(77,r['exit'])
        cap = capture.loads(capture.decode_stream(r['stdout'])['capture.json'])
        self.assertEqual('NOT_RUN',cap['status']);self.assertFalse(cap['qnx_executed'])

    def test_host_native_adapter_preserves_not_run(self):
        r = capture.run_native(SCENARIO,'reference',self.root/'native',str(BIN))
        self.assertEqual('NOT_RUN',r['verdict']);self.assertFalse(r['qnx_executed'])

    def test_full_host_acceptance_cannot_pass_on_linux(self):
        r = native_workflow.acceptance(BIN,self.root/'accept',collector=True)
        self.assertEqual('NOT_RUN',r['status']);self.assertFalse(r['native_gate_closed'])

    def test_missing_launcher_is_not_run(self):
        r = capture.run_native(SCENARIO,'reference',self.root/'missing',str(self.root/'not-binaries'))
        self.assertEqual('NOT_RUN',r['verdict'])

    def test_no_overwrite_of_existing_output_directory(self):
        dest=self.root/'occupied';dest.mkdir();(dest/'sentinel').write_text('untouched')
        cmd = [str(BIN/'dl-capture'),'--bin',str(BIN),'--mode','normal','--calls','1:10',
               '--token',TOKEN,'--out',str(dest),'--transport-fixture']
        r = capture.execute(cmd, timeout=3)
        self.assertEqual(73,r['exit']);self.assertEqual('untouched',(dest/'sentinel').read_text())

    def test_malformed_call_numbers_rejected_without_starting_children(self):
        for calls in ('-1:20','1:0','1001:2','1:5001','1:2,','1:2,,1:2','999999999999999999999:2'):
            cmd=[str(BIN/'dl-capture'),'--bin',str(BIN),'--mode','normal','--calls',calls,
                 '--token',TOKEN,'--stream','--transport-fixture']
            r=capture.execute(cmd,timeout=3)
            self.assertEqual(64,r['exit']);self.assertEqual(b'',r['stdout'])

    def test_host_bounds_output_and_reaps_launcher(self):
        r=capture.execute([sys.executable,'-S','-c','import sys;sys.stdout.buffer.write(b"x"*4000000)'],timeout=3)
        self.assertIsNotNone(r['error']);self.assertTrue(r['launcher_reaped'])
        self.assertLessEqual(len(r['stdout']),capture.MAX_STREAM)

    def test_host_times_out_stalled_launcher(self):
        r=capture.execute([sys.executable,'-S','-c','import time;time.sleep(10)'],timeout=0.1)
        self.assertIn('deadline',r['error']);self.assertTrue(r['launcher_reaped'])

    def test_interrupt_reaps_child_and_records_incomplete(self):
        out=self.root/'interrupted'
        cmd=[str(BIN/'dl-capture'),'--bin',str(BIN),'--mode','partial','--calls','1:10',
             '--token',TOKEN,'--out',str(out),'--transport-fixture']
        process=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+2
            while time.monotonic()<deadline and not (out/'server.jsonl').exists(): time.sleep(.005)
            self.assertTrue((out/'server.jsonl').exists())
            process.send_signal(signal.SIGTERM)
            stdout,stderr=process.communicate(timeout=3)
            self.assertEqual(78,process.returncode)
            cap=capture.loads((out/'capture.json').read_bytes())
            self.assertEqual('INCOMPLETE',cap['status']);self.assertEqual(signal.SIGTERM,cap['interrupted'])
            self.assertTrue(cap['server_reaped'])
            with self.assertRaises(ProcessLookupError):os.kill(cap['server_pid'],0)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=2)
            process.stdout.close();process.stderr.close()

    def test_eight_calls_plus_required_healthy_probe(self):
        scenario={**SCENARIO,'actions':SCENARIO['actions']*8}
        r,files,cap=self.collect(scenario=scenario)
        self.assertEqual(0,r['exit']);self.assertEqual(9,len(cap['calls']))
        self.assertIn('client-9.stdout',files)


class WorkflowDispatchTests(unittest.TestCase):
    def test_host_capture_dispatch_does_not_use_python_target_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('deadline_lab.capture.run_native',return_value={'verdict':'NOT_RUN'}) as runner:
                native_workflow.execute_case(SCENARIO,'reference',Path(tmp)/'case',Path('/target/bin'),True,'qnx-lab')
                runner.assert_called_once_with(SCENARIO,'reference',Path(tmp)/'case','/target/bin',ssh='qnx-lab')

    def test_missing_target_is_junit_error_not_success_or_skip(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);capture.write(root/'case.json',SCENARIO)
            capture.write(root/'suite.json',{'schema':3,'adapter':'qnx-native','cases':[
                {'name':'capture','scenario':'case.json','property':'cancel_before_effect','sensitivity_mode':'ignore_unblock'}]})
            result=native_workflow.regress(root/'suite.json',root/'out',BIN,collector=True,sensitivity=True)
            self.assertFalse(result['passed']);self.assertFalse(result['qnx_executed']);self.assertEqual(2,result['inconclusive'])
            tree=ET.parse(root/'out'/'junit.xml')
            self.assertEqual(2,len(tree.findall('.//error')));self.assertEqual(0,len(tree.findall('.//skipped')))

    def test_ssh_not_silently_ignored_without_collector(self):
        with self.assertRaises(ValueError):
            native_workflow.execute_case(SCENARIO,'reference',Path('/unused'),Path('/unused'),ssh='qnx-lab')
