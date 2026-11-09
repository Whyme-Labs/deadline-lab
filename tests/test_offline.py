"""Real portable handoffs. None of these tests emulate QNX APIs."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from deadline_lab import capture, offline
from deadline_lab.adapters.qnx_native import DEFAULT_SCENARIO

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.environ.get('DL_CAPTURE_TEST_BIN', str(ROOT / 'build'))).resolve()
SCALE = int(os.environ.get('DL_CAPTURE_BUDGET_SCALE', '1'))


@unittest.skipUnless((BIN / 'dl-capture').exists(), 'build the portable C collector first')
class OfflineHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dl offline ' ")
        self.root = Path(self.temp.name)
        self.handoff = self.root / 'handoff with spaces'
        self.result = self.root / 'capture results'
        self.summary = offline.prepare(BIN, self.handoff, DEFAULT_SCENARIO, 'normal',
                                       fixture=True, budget_ms=1200 * SCALE)

    def tearDown(self):
        self.temp.cleanup()

    def execute(self, target=None):
        target = target or self.handoff / 'target'
        # Exercise the generated script exactly as an operator would.
        return subprocess.run([str(target / 'run-target.sh'), str(self.result)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=12 * SCALE, cwd=self.root)

    def imported(self, out='imported'):
        return offline.ingest(self.handoff / 'request.json', self.result, self.root / out)

    def test_prepare_run_import_and_offline_record_integrity(self):
        self.assertEqual('TRANSPORT_TEST_READY', self.summary['status'])
        self.assertEqual(0, self.execute().returncode)
        result = self.imported()
        self.assertEqual('TRANSPORT_ONLY', result['verdict'])
        self.assertEqual(1, result['observed_effects'])
        self.assertFalse(result['qnx_executed'])
        self.assertFalse(result['native_gate_closed'])
        self.assertFalse(result['native_provenance_verified'])
        from deadline_lab.evidence import verify
        verify(self.root / 'imported', {'offline-request.json','capture.exit','transport.stdout'})
        tr = json.loads((self.root / 'imported' / 'transport.json').read_text())
        self.assertFalse(tr['host_observed_launcher'])
        self.assertNotIn('launcher_reaped', tr)

    def test_relocated_bundle_runs_without_host_source_on_path(self):
        moved = self.root / "relocated ' target"
        shutil.copytree(self.handoff / 'target', moved)
        self.assertEqual(0, self.execute(moved).returncode)
        self.assertEqual('TRANSPORT_ONLY', self.imported()['verdict'])

    def test_relocated_target_path_has_only_mkdir(self):
        tools=self.root/'only-target-utility';tools.mkdir()
        (tools/'mkdir').symlink_to(shutil.which('mkdir'))
        target=self.root/'minimal target';shutil.copytree(self.handoff/'target',target)
        done=subprocess.run([str(target/'run-target.sh'),str(self.result)],
                            capture_output=True,timeout=12*SCALE,cwd=self.root,
                            env={**os.environ,'PATH':str(tools)})
        self.assertEqual(0,done.returncode,done.stderr.decode())
        self.assertEqual('TRANSPORT_ONLY',self.imported()['verdict'])

    def test_malformed_request_identity_types_are_rejected(self):
        original=json.loads((self.handoff/'request.json').read_text())
        for key,value in [('expected_binaries',None),('expected_metadata',[]),
                          ('expected_source_set_sha256',123),('fixture','yes')]:
            doc=copy.deepcopy(original);doc['request'][key]=value
            doc['request_sha256']=offline.digest(offline.canonical(doc['request']))
            with self.subTest(key=key),self.assertRaises(ValueError):
                offline.checked_request(json.dumps(doc).encode())

    def test_binary_set_is_exact_and_only_project_files(self):
        self.assertEqual(set(offline.binaries(True)) | set(offline.METADATA) | {'run-target.sh'},
                         {p.name for p in (self.handoff / 'target').iterdir()})
        self.assertFalse((self.handoff / 'target' / 'request.json').exists())

    def test_missing_native_build_never_creates_ready_bundle(self):
        out = self.root / 'not-native'
        with self.assertRaises(FileNotFoundError):
            offline.prepare(BIN, out, DEFAULT_SCENARIO)
        self.assertFalse(out.exists())

    def test_incomplete_capture_cannot_pass_by_editing_exit(self):
        bad = self.root / 'partial-handoff'
        offline.prepare(BIN, bad, DEFAULT_SCENARIO, 'partial', fixture=True, budget_ms=250 * SCALE)
        done = subprocess.run([str(bad / 'target/run-target.sh'),str(self.result)],
                              capture_output=True, timeout=10 * SCALE)
        self.assertEqual(78, done.returncode)
        (self.result / 'capture.exit').write_text('0\n')
        result = offline.ingest(bad / 'request.json', self.result, self.root / 'partial-import')
        self.assertEqual('INCONCLUSIVE', result['verdict'])

    def test_new_ticket_rejects_old_result(self):
        self.assertEqual(0,self.execute().returncode)
        second = self.root / 'new-ticket'
        offline.prepare(BIN, second, DEFAULT_SCENARIO, 'normal', fixture=True)
        result = offline.ingest(second / 'request.json',self.result,self.root / 'wrong-ticket')
        self.assertEqual('INCONCLUSIVE',result['verdict'])
        self.assertIn('different host request',result['reason'])

    def test_changed_target_binary_is_detected_against_host_pin(self):
        binary = self.handoff / 'target/dl-transport-client'
        with binary.open('ab') as f: f.write(b'changed after preparation')
        self.assertEqual(0,self.execute().returncode)
        result=self.imported()
        self.assertEqual('INCONCLUSIVE',result['verdict'])
        self.assertIn('differs from prepared host',result['reason'])

    def test_truncated_capture_is_inconclusive(self):
        self.execute()
        p=self.result/'capture.stdout';p.write_bytes(p.read_bytes()[:-2])
        self.assertEqual('INCONCLUSIVE',self.imported()['verdict'])

    def test_missing_completion_is_inconclusive_with_raw_bytes_retained(self):
        self.execute();(self.result/'capture.exit').unlink()
        self.assertEqual('INCONCLUSIVE',self.imported()['verdict'])
        self.assertTrue((self.root/'imported/transport.stdout').exists())

    def test_stderr_is_not_ignored(self):
        self.execute();(self.result/'capture.stderr').write_bytes(b'target error\n')
        self.assertEqual('INCONCLUSIVE',self.imported()['verdict'])

    def test_bad_exit_values_are_rejected(self):
        self.execute()
        for i,value in enumerate(('00\n','-1\n','256\n','0','nan\n')):
            (self.result/'capture.exit').write_text(value)
            self.assertEqual('INCONCLUSIVE',self.imported('exit-'+str(i))['verdict'])

    def test_completion_symlink_is_rejected(self):
        self.execute()
        p=self.result/'capture.exit';p.unlink()
        other=self.root/'fake-exit';other.write_text('0\n');p.symlink_to(other)
        self.assertEqual('INCONCLUSIVE',self.imported()['verdict'])

    def test_request_corruption_is_rejected_before_import(self):
        doc=json.loads((self.handoff/'request.json').read_text())
        doc['request']['mode']='burst'
        (self.handoff/'request.json').write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError,'digest mismatch'): self.imported()
        self.assertFalse((self.root/'imported').exists())

    def test_script_does_not_overwrite_an_existing_result(self):
        self.result.mkdir();(self.result/'sentinel').write_text('keep')
        self.assertNotEqual(0,self.execute().returncode)
        self.assertEqual('keep',(self.result/'sentinel').read_text())
        self.assertFalse((self.result/'capture.stdout').exists())

    def test_script_does_not_follow_existing_result_link(self):
        actual=self.root/'actual';actual.mkdir();self.result.symlink_to(actual,target_is_directory=True)
        self.assertNotEqual(0,self.execute().returncode)
        self.assertEqual([],list(actual.iterdir()))

    def test_prepare_and_import_do_not_overwrite_existing_directories(self):
        with self.assertRaises(FileExistsError):
            offline.prepare(BIN,self.handoff,DEFAULT_SCENARIO,'normal',fixture=True)
        self.execute();self.imported()
        with self.assertRaises(FileExistsError): self.imported()

    def test_binary_symlinks_are_rejected_before_copy(self):
        inputs=self.root/'binary-links';inputs.mkdir()
        for name in offline.binaries(True): (inputs/name).symlink_to(BIN/name)
        with self.assertRaises(OSError):
            offline.prepare(inputs,self.root/'rejected',DEFAULT_SCENARIO,'normal',fixture=True)
        self.assertFalse((self.root/'rejected').exists())

    def test_requests_pin_all_binary_and_metadata_bytes(self):
        r=offline.checked_request((self.handoff/'request.json').read_bytes())
        for group in ('expected_binaries','expected_metadata'):
            for name,identity in r[group].items():
                data=(self.handoff/'target'/name).read_bytes()
                self.assertEqual({'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)},identity)

    def test_native_metadata_checker_rejects_internally_consistent_replacement(self):
        # Unit-level metadata check only, not a genuine native capture.
        self.execute()
        files=capture.decode_stream((self.result/'capture.stdout').read_bytes())
        r=offline.checked_request((self.handoff/'request.json').read_bytes())
        r=copy.deepcopy(r);r['fixture']=False
        for name in offline.METADATA: files[name]=(self.handoff/'target'/name).read_bytes()
        files['build-record.json']+=b' '
        with self.assertRaisesRegex(ValueError,'metadata differs'):
            offline.check_pinned_capture(files,r)

    def test_portable_capture_never_enters_native_materializer(self):
        self.execute()
        files=capture.decode_stream((self.result/'capture.stdout').read_bytes())
        r=offline.checked_request((self.handoff/'request.json').read_bytes())
        with self.assertRaisesRegex(ValueError,'genuine native'):
            capture.native_material(files,r)

    def test_fifo_reader_refuses_without_blocking(self):
        p=self.root/'fifo';os.mkfifo(p)
        with self.assertRaises(ValueError):offline.read_regular(p,64)

    def test_large_result_file_is_rejected(self):
        self.execute()
        p=self.result/'capture.stdout'
        with p.open('wb') as f:f.truncate(capture.MAX_STREAM+1)
        self.assertEqual('INCONCLUSIVE',self.imported()['verdict'])

    def test_wrong_wrapper_argument_count_writes_nothing(self):
        done=subprocess.run([str(self.handoff/'target/run-target.sh')],capture_output=True,timeout=3)
        self.assertEqual(64,done.returncode)
        self.assertFalse(self.result.exists())

    def test_host_request_is_required_for_native_offline_recheck(self):
        self.execute();self.imported()
        r=offline.checked_request((self.handoff/'request.json').read_bytes())
        tr={'origin':'offline-file','import_complete':True,'host_observed_launcher':False,'exit':0}
        with self.assertRaisesRegex(ValueError,'original native host request'):
            offline.verify_offline_import(self.root/'imported',r,tr)
