"""Real local pipe/process tests and explicitly synthetic checker fixtures."""
import errno
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from deadline_lab.bounded_io import LineReader
from deadline_lab.reducer import reduce_actions
from deadline_lab import native_build, native_gate, source_manifest, native_workflow
from deadline_lab.adapters import qnx_native as q
from deadline_lab.evidence import seal
from deadline_lab.trace import read_trace
from test_native_evidence import fixture

ROOT = Path(__file__).resolve().parents[1]


class BoundedPipeTests(unittest.TestCase):
    def setUp(self):
        self.r, self.w = os.pipe()
        self.reader = LineReader(self.r, 16)
    def tearDown(self):
        os.close(self.r)
        if self.w >= 0: os.close(self.w)
    def test_partial_greeting_does_not_block_forever(self):
        os.write(self.w, b'READY')
        start = time.monotonic()
        self.assertIsNone(self.reader.read(.04))
        self.assertLess(time.monotonic() - start, 1)
        os.write(self.w, b'\n')
        self.assertEqual('READY', self.reader.read(.04))
    def test_multiple_lines_retained(self):
        os.write(self.w, b'one\ntwo\n')
        self.assertEqual('one', self.reader.read(.1))
        self.assertEqual('two', self.reader.read(.1))
    def test_oversized_line_without_newline(self):
        os.write(self.w, b'x' * 17)
        with self.assertRaises(ValueError): self.reader.read(.1)
    def test_eof_is_not_success(self):
        os.write(self.w, b'READY')
        os.close(self.w); self.w = -1
        with self.assertRaises(EOFError): self.reader.read(.1)
    def test_non_ascii_rejected(self):
        os.write(self.w, b'\xff\n')
        with self.assertRaises(UnicodeError): self.reader.read(.1)
    def test_invalid_timeout(self):
        for bad in [0, -1, float('inf'), float('nan'), True]:
            with self.assertRaises(ValueError): self.reader.read(bad)
    def test_deliberately_hung_child_can_be_reaped(self):
        p = subprocess.Popen([sys.executable, '-S', '-c',
            'import os,time; os.write(1,b"READY"); time.sleep(30)'], stdout=subprocess.PIPE, bufsize=0)
        try:
            self.assertIsNone(LineReader(p.stdout.fileno()).read(.15))
        finally:
            p.kill(); p.wait(timeout=2); p.stdout.close()
        self.assertIsNotNone(p.returncode)


class ReductionEvidenceTests(unittest.TestCase):
    def validate(self, s):
        if not s['actions']: raise ValueError('empty history')
    def scenario(self): return {'actions': [{'op': 'a'}, {'op': 'b'}]}
    def run_with(self, verdict):
        def runner(s, out):
            return {'verdict': 'FAIL', 'properties': ['p']} if len(s['actions']) == 2 else {
                'verdict': verdict, 'properties': []}
        return reduce_actions(self.scenario(), runner, self.validate, 'p')
    def test_inconclusive_deletion_does_not_prove_minimality(self):
        _, record = self.run_with('INCONCLUSIVE')
        self.assertIsNone(record['deletion_1_minimal'])
        self.assertEqual('INCONCLUSIVE', record['minimality_status'])
        self.assertTrue(record['final_reproduces'])
    def test_not_run_deletion_does_not_prove_minimality(self):
        _, record = self.run_with('NOT_RUN')
        self.assertIsNone(record['deletion_1_minimal'])
        self.assertGreater(record['not_run_candidates'], 0)
    def test_conclusive_nonfailures_support_minimality(self):
        _, record = self.run_with('PASS')
        self.assertIs(record['deletion_1_minimal'], True)
        self.assertEqual(2, len(record['deletion_audit']))
    def test_original_unknown_cannot_be_a_witness(self):
        with self.assertRaises(RuntimeError):
            reduce_actions(self.scenario(), lambda s,p: {'verdict':'INCONCLUSIVE'}, self.validate, 'p')
    def test_budget_exhaustion_is_not_a_minimality_claim(self):
        with self.assertRaises(RuntimeError):
            reduce_actions(self.scenario(), lambda s,p: {'verdict':'FAIL','properties':['p']},
                           self.validate, 'p', max_executions=2)


class NativeHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_missing_sdk_is_not_a_successful_build(self):
        with patch.dict(os.environ, {'PATH':'/does-not-exist','QNX_HOST':'','QNX_TARGET':''}):
            r = native_build.build(self.root/'build', 'gcc_ntox86_64')
        self.assertEqual('NOT_RUN', r['status']); self.assertFalse(r['qnx_compiled'])
        self.assertIn('qcc', r['missing'])
    def test_invalid_toolchain_variant_rejected(self):
        with self.assertRaises(ValueError): native_build.build(self.root/'build','x; echo bad')
    def test_no_sdk_directory_leaks_from_preflight(self):
        r = native_build.prerequisites()
        self.assertNotIn('QNX_HOST=',json.dumps(r))
    def test_linux_guard_stays_closed(self):
        if sys.platform.startswith('linux'):
            r = q.run(q.DEFAULT_SCENARIO,'reference',self.root/'run',self.root)
            self.assertEqual('NOT_RUN',r['verdict'])
    def test_full_native_workflow_declines_linux(self):
        if sys.platform.startswith('linux'):
            r=native_workflow.acceptance(self.root/'bins',self.root/'accept')
            self.assertEqual('NOT_RUN',r['status']);self.assertFalse(r['native_gate_closed'])
    def test_native_regressions_emit_errors_not_false_pass_on_linux(self):
        if not sys.platform.startswith('linux'): self.skipTest('Linux guard only')
        (self.root/'case.json').write_text(json.dumps(q.DEFAULT_SCENARIO))
        (self.root/'suite.json').write_text(json.dumps({'schema':3,'adapter':'qnx-native','cases':[
            {'name':'case','scenario':'case.json','property':'cancel_before_effect',
             'sensitivity_mode':'ignore_unblock'}]}))
        r=native_workflow.regress(self.root/'suite.json',self.root/'out',self.root,sensitivity=True)
        self.assertFalse(r['passed']);self.assertEqual(2,r['inconclusive'])
        self.assertIn('errors="2"',(self.root/'out/junit.xml').read_text())
    def test_native_suite_path_escape_rejected(self):
        (self.root/'suite.json').write_text(json.dumps({'schema':3,'adapter':'qnx-native','cases':[
            {'name':'case','scenario':'../case.json','property':'cancel_before_effect',
             'sensitivity_mode':'ignore_unblock'}]}))
        with self.assertRaises(ValueError):
            native_workflow.regress(self.root/'suite.json',self.root/'out',self.root)
    def test_missing_campaign_does_not_pass(self):
        self.assertFalse(native_gate.assess(self.root)['native_gate_closed'])
    def test_forged_success_summary_cannot_pass(self):
        (self.root/'summary.json').write_text(json.dumps({'schema':3,'qnx_executed':True,
            'expectations_met':True,'repetitions':5,'runs':[]}))
        self.assertFalse(native_gate.assess(self.root)['native_gate_closed'])
    def test_synthetic_passing_records_cannot_close_native_gate(self):
        runs=[]
        for i in range(5):
            for mode in ('reference','ignore_unblock'):
                name=f'{i}-{mode}';fixture(self.root/name,broken=mode=='ignore_unblock')
                runs.append({'path':name,'policy':mode,'repetition':i})
        (self.root/'summary.json').write_text(json.dumps({'schema':3,'qnx_executed':True,
             'repetitions':5,'runs':runs}))
        r=native_gate.assess(self.root)
        self.assertEqual(10,r['runs_rechecked']);self.assertFalse(r['native_gate_closed'])
    def test_relabelled_synthetic_record_lacks_native_provenance(self):
        p=fixture(self.root/'case');t=json.loads((p/'target.json').read_text())
        t.update(evidence_origin='native-qnx',system='QNX')
        (p/'target.json').write_text(json.dumps(t));seal(p,sorted(q.REQUIRED))
        self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_commit_before_unblock_is_not_retroactive_cancellation(self):
        p=fixture(self.root/'case',broken=True)
        e=[json.loads(x) for x in (p/'server.jsonl').read_text().splitlines()]
        for row in e:
            if row['kind']=='unblock_observed': row['monotonic_ns']=180
        e.sort(key=lambda r:r['monotonic_ns'])
        (p/'server.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in e))
        seal(p,sorted(q.REQUIRED))
        r=q.evaluate(p)
        self.assertEqual('INCONCLUSIVE',r['verdict'])
        self.assertNotIn('cancel_before_effect',r['properties'])
    def test_malformed_target_object_is_inconclusive(self):
        p=fixture(self.root/'case');(p/'target.json').write_text('[]')
        seal(p,sorted(q.REQUIRED))
        self.assertEqual('INCONCLUSIVE',q.evaluate(p)['verdict'])
    def test_relabelled_origin_does_not_claim_qnx_execution(self):
        p=fixture(self.root/'case');t=json.loads((p/'target.json').read_text())
        t['evidence_origin']='native-qnx';(p/'target.json').write_text(json.dumps(t))
        seal(p,sorted(q.REQUIRED))
        self.assertFalse(q.evaluate(p)['qnx_executed'])
    def test_native_minimum_cannot_be_weakened_to_one(self):
        with self.assertRaises(ValueError): native_gate.assess(self.root,1)
    def test_wrong_architecture_elf_rejected(self):
        p=self.root/'elf';p.write_bytes(b'not an elf')
        with self.assertRaises(ValueError):native_build.check_elf(p,'gcc_ntox86_64')


class DistributionTests(unittest.TestCase):
    def test_package_does_not_promote_summary_only_native_claims(self):
        spec=importlib.util.spec_from_file_location('dl_native_packager',ROOT/'scripts/package-release.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';root.mkdir()
            for source in source_manifest.source_paths(ROOT):
                p=root/source.relative_to(ROOT);p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(source.read_bytes())
            canary=root/'evidence'/'native'/'canary';canary.mkdir(parents=True)
            (canary/'summary.json').write_text(json.dumps({
                'schema':3,'qnx_executed':True,'repetitions':5,'runs':[], 'results':[]}))
            out=Path(temp)/'unproven.zip'
            with self.assertRaisesRegex(ValueError,'independent verification'):
                mod.create(root,out,evidence=True,native_canary=canary)
            self.assertFalse(out.exists())

    def test_manifest_contains_documented_build_helper(self):
        m=source_manifest.manifest(ROOT)
        self.assertIn('scripts/build-qnx.sh',m['files'])
    def test_source_archive_readback_and_executable_modes(self):
        spec=importlib.util.spec_from_file_location('dl_packager',ROOT/'scripts/package-release.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'source.zip';r=mod.create(ROOT,p)
            self.assertTrue(r['readback_verified'])
            with zipfile.ZipFile(p) as archive:
                entry=archive.getinfo('deadline-lab/scripts/build-qnx.sh')
                self.assertEqual(0o755,entry.external_attr>>16 & 0o777)
                archive.extractall(Path(temp)/'extract')
            source_manifest.verify(Path(temp)/'extract/deadline-lab',source_manifest.manifest(ROOT))
    def test_offline_completion_record_is_in_evidence_package(self):
        spec=importlib.util.spec_from_file_location('dl_offline_packager',ROOT/'scripts/package-release.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';root.mkdir()
            for source in source_manifest.source_paths(ROOT):
                p=root/source.relative_to(ROOT);p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(source.read_bytes())
            evidence=root/'evidence'/'offline';evidence.mkdir(parents=True)
            # Include invalid text too: export must retain evidence of a bad import.
            record=evidence/'capture.exit';record.write_bytes(b'256\n')
            out=Path(temp)/'evidence.zip';result=mod.create(root,out,evidence=True)
            self.assertTrue(result['readback_verified'])
            with zipfile.ZipFile(out) as z:
                self.assertEqual(b'256\n',z.read('deadline-lab/evidence/offline/capture.exit'))

    def test_completion_allowlist_stays_narrow_and_bounded(self):
        spec=importlib.util.spec_from_file_location('dl_exit_packager',ROOT/'scripts/package-release.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';root.mkdir()
            for source in source_manifest.source_paths(ROOT):
                p=root/source.relative_to(ROOT);p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(source.read_bytes())
            evidence=root/'evidence';evidence.mkdir()
            p=evidence/'capture.exit';p.write_bytes(b'x'*65)
            with self.assertRaisesRegex(ValueError,'unreviewed evidence'):
                mod.create(root,Path(temp)/'oversized.zip',evidence=True)
            p.unlink();(evidence/'other.exit').write_bytes(b'0\n')
            with self.assertRaisesRegex(ValueError,'unreviewed evidence'):
                mod.create(root,Path(temp)/'unknown.zip',evidence=True)

    def test_distribution_does_not_depend_on_git(self):
        with patch.dict(os.environ,{'PATH':'/not-here'}):
            self.assertGreater(len(source_manifest.manifest(ROOT)['files']),60)


class ObserverFramingTests(unittest.TestCase):
    def test_oversized_effect_fails_without_waiting_for_eof(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,w=os.pipe();out=Path(tmp)/'effects.jsonl'
            p=subprocess.Popen([sys.executable,'-S','-m','deadline_lab.plant','--fd',str(r),
                '--out',str(out)],cwd=ROOT,pass_fds=(r,),stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
            os.close(r)
            try:
                self.assertEqual('READY',LineReader(p.stdout.fileno()).read(2))
                os.write(w,b'x'*257)
                # Writer intentionally stays open: the framing limit, not EOF, must stop it.
                p.wait(timeout=2)
                self.assertEqual(2,p.returncode)
                with self.assertRaises(ValueError):read_trace(out)
                self.assertIn('oversized effect frame',out.read_text())
            finally:
                os.close(w)
                if p.poll() is None:p.kill();p.wait(timeout=2)
                p.stdout.close();p.stderr.close()
