#!/usr/bin/env python3
"""Retain a small real portable handoff trial, never a QNX acceptance campaign."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deadline_lab import capture, offline
from deadline_lab.adapters.qnx_native import DEFAULT_SCENARIO
from deadline_lab.evidence import verify

ROOT = Path(__file__).resolve().parents[1]


def rehearse(binaries: Path, out: Path) -> dict:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    outcomes = []
    with tempfile.TemporaryDirectory(prefix="dl offline rehearsal ' ") as tmp:
        staging = Path(tmp)
        utilities = staging / 'only-target-utility'
        utilities.mkdir()
        (utilities / 'mkdir').symlink_to(shutil.which('mkdir'))
        good_request = None
        normal_raw = None
        for name, mode in [('normal', 'normal'), ('relocated', 'normal'),
                           ('changed_binary', 'normal'), ('stalled_child', 'partial')]:
            handoff = staging / name
            offline.prepare(binaries, handoff, DEFAULT_SCENARIO, mode,
                            fixture=True, budget_ms=350 if mode == 'partial' else 1200)
            target = handoff / 'target'
            if name == 'relocated':
                moved = staging / "independent directory ' target"
                target.rename(moved)
                target = moved
            if name == 'changed_binary':
                with (target / 'dl-transport-client').open('ab') as stream:
                    stream.write(b'Changed after trusted host preparation.\n')
            case = out / name
            case.mkdir()
            shutil.copyfile(handoff / 'request.json', case / 'host-request.json')
            script = target / 'run-target.sh'
            result_dir = case / 'returned'
            process = subprocess.run([str(script), str(result_dir)], capture_output=True,
                                     timeout=8, cwd=staging,
                                     env={**os.environ, 'PATH':str(utilities)})
            capture.write(case / 'execution.json', {
                'schema': 1, 'evidence_origin': 'posix-offline-handoff',
                'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
                'exit': process.returncode, 'stdout': process.stdout.decode('utf-8', 'replace'),
                'stderr': process.stderr.decode('utf-8', 'replace'),
                'target_was_relocated': name == 'relocated',
                'target_path_programs': ['mkdir'], 'qnx_executed': False})
            verdict = offline.ingest(case / 'host-request.json', result_dir, case / 'imported')
            expected = 'TRANSPORT_ONLY' if name in {'normal', 'relocated'} else 'INCONCLUSIVE'
            outcomes.append({'name': name, 'actual': verdict['verdict'], 'expected': expected,
                             'met': verdict['verdict'] == expected and not verdict['qnx_executed'],
                             'real_capture_executed': True, 'capture_exit': process.returncode})
            if name == 'normal':
                good_request = case / 'host-request.json'
                normal_raw = result_dir
        # These four checks edit/reassociate returned files. They are imports,
        # not additional collector process executions or fault discoveries.
        for name in ('different_request', 'truncated', 'missing_completion', 'diagnostics'):
            case = out / name
            case.mkdir()
            results = case / 'returned'
            shutil.copytree(normal_raw, results)
            if name == 'different_request':
                h = staging / 'different_request'
                offline.prepare(binaries, h, DEFAULT_SCENARIO, 'normal', fixture=True)
                req = h / 'request.json'
            else:
                req = good_request
            shutil.copyfile(req, case / 'host-request.json')
            if name == 'truncated':
                p = results / 'capture.stdout'; p.write_bytes(p.read_bytes()[:-2])
            elif name == 'missing_completion':
                (results / 'capture.exit').unlink()
            elif name == 'diagnostics':
                (results / 'capture.stderr').write_bytes(b'Injected transfer diagnostic\n')
            verdict = offline.ingest(case / 'host-request.json', results, case / 'imported')
            outcomes.append({'name': name, 'actual': verdict['verdict'], 'expected': 'INCONCLUSIVE',
                             'met': verdict['verdict'] == 'INCONCLUSIVE' and not verdict['qnx_executed'],
                             'real_capture_executed': False})
        # Verify retained imported-file manifests. This is an offline check only.
        for case in outcomes:
            verify(out / case['name'] / 'imported', {'offline-request.json','invocation.json'})
    summary = {'schema': 1, 'milestone': 'offline handoff transport rehearsal',
               'qnx_executed': False, 'native_gate_closed': False,
               'real_collector_captures': 4, 'additional_import_checks': 4,
               'expected_outcomes': len(outcomes), 'met': sum(c['met'] for c in outcomes),
               'imported_manifests_verified': len(outcomes),
               'staging_removed': not Path(tmp).exists(), 'cases': outcomes,
               'bounds': ['Linux POSIX collector/fixture execution, not QNX API emulation.',
                          'Metadata pin validation for a real native build remains unexecuted.',
                          'No SSH, licensed SDK, physical actuator or outside developer trial.']}
    capture.write(out / 'summary.json', summary)
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bin', type=Path, default=ROOT / 'build')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = rehearse(a.bin.resolve(), a.out)
    print(json.dumps(result, indent=2))
    return 0 if result['met'] == result['expected_outcomes'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
