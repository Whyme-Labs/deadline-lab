"""Native acceptance -> reduction -> exported regression, only on actual QNX.

This entry point cannot close the native gate on Linux. A failed prerequisite is
recorded and returned as 77, never recast as a successful native verification.
"""
from __future__ import annotations
import argparse
import json
import platform
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from .adapters.qnx_native import run, validate
from .native_gate import assess
from .reducer import reduce_actions

NOISY_SCENARIO = {'schema': 2, 'adapter': 'qnx-native', 'name': 'native-cancel-with-surrounding-work',
    'actions': [
        {'op': 'call', 'work_ms': 1, 'timeout_ms': 1500, 'expect_unblock': False},
        {'op': 'call', 'work_ms': 150, 'timeout_ms': 25, 'expect_unblock': True},
        {'op': 'call', 'work_ms': 1, 'timeout_ms': 1500, 'expect_unblock': False},
        {'op': 'call', 'work_ms': 200, 'timeout_ms': 30, 'expect_unblock': True},
        {'op': 'call', 'work_ms': 1, 'timeout_ms': 1500, 'expect_unblock': False},
    ]}


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def regress(suite_path: Path, out: Path, bin_dir: Path,
            candidate: str = 'reference', sensitivity: bool = False) -> dict:
    if candidate not in {'reference', 'ignore_unblock'}:
        raise ValueError('unknown native candidate')
    suite = json.loads(suite_path.read_text())
    if suite.get('schema') != 3 or suite.get('adapter') != 'qnx-native':
        raise ValueError('invalid native regression suite')
    specs = suite.get('cases')
    if not isinstance(specs, list) or not 1 <= len(specs) <= 8:
        raise ValueError('native suite needs 1..8 cases')
    loaded = []
    root = suite_path.resolve().parent
    for spec in specs:
        name = spec.get('scenario')
        if not isinstance(name, str) or Path(name).name != name or name in {'.', '..'}:
            raise ValueError('native scenario must be a sibling file')
        path = root / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('native scenario missing or symlink')
        scenario = json.loads(path.read_text()); validate(scenario)
        if spec.get('property') != 'cancel_before_effect' or spec.get('sensitivity_mode') != 'ignore_unblock':
            raise ValueError('unsupported native property or negative control')
        if not isinstance(spec.get('name'), str) or not spec['name']:
            raise ValueError('missing regression name')
        loaded.append((spec, scenario))
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for i, (spec, scenario) in enumerate(loaded):
        choices = [(candidate, 'candidate')]
        if sensitivity:
            choices.append(('ignore_unblock', 'sensitivity'))
        for mode, purpose in choices:
            result = run(scenario, mode, out / f'{i}-{purpose}', bin_dir)
            expected = (result['verdict'] == 'PASS' if purpose == 'candidate' else
                        result['verdict'] == 'FAIL' and spec['property'] in result['properties'])
            # Synthetic success is not native regression success.
            expected = expected and result.get('qnx_executed') is True
            rows.append({'name': spec['name'], 'purpose': purpose, 'mode': mode,
                         'expected_outcome_observed': expected, 'result': result})
    unknown = sum(r['result']['verdict'] in {'INCONCLUSIVE', 'NOT_RUN'} for r in rows)
    failed = sum(not r['expected_outcome_observed'] for r in rows)
    summary = {'schema': 3, 'adapter': 'qnx-native', 'checks': len(rows),
               'passed': failed == 0, 'failed_expectations': failed, 'inconclusive': unknown,
               'qnx_executed': bool(rows) and all(r['result'].get('qnx_executed') is True for r in rows),
               'cases': rows}
    write(out / 'summary.json', summary)
    xml = ET.Element('testsuite', name='deadline-lab.native', tests=str(len(rows)),
                     failures=str(failed - unknown), errors=str(unknown))
    for row in rows:
        case = ET.SubElement(xml, 'testcase', classname='deadline_lab.qnx',
                             name=row['name'] + '.' + row['purpose'])
        if not row['expected_outcome_observed']:
            tag = 'error' if row['result']['verdict'] in {'INCONCLUSIVE', 'NOT_RUN'} else 'failure'
            ET.SubElement(case, tag, message='Expected native outcome not observed').text = json.dumps(row['result'])
        ET.SubElement(case, 'system-out').text = json.dumps(row['result'])
    ET.ElementTree(xml).write(out / 'junit.xml', encoding='utf-8', xml_declaration=True)
    return summary


def acceptance(bin_dir: Path, out: Path, repetitions: int = 5) -> dict:
    if type(repetitions) is not int or not 5 <= repetitions <= 20:
        raise ValueError('acceptance requires 5..20 paired repetitions')
    out.mkdir(parents=True, exist_ok=False)
    if platform.system() != 'QNX':
        result = {'schema': 1, 'status': 'NOT_RUN', 'native_gate_closed': False,
                  'qnx_executed': False, 'host': platform.system(),
                  'reason': 'Run on an authorised QNX target with the licensed build outputs.'}
        write(out / 'acceptance.json', result)
        return result
    campaign = out / 'canary'; campaign.mkdir()
    runs, results = [], []
    for i in range(repetitions):
        for mode in ('reference', 'ignore_unblock'):
            name = f'{i}-{mode}'
            result = run(NOISY_SCENARIO, mode, campaign / name, bin_dir)
            results.append(result); runs.append({'path': name, 'repetition': i, 'policy': mode})
            if result['verdict'] == 'NOT_RUN':
                write(campaign / 'summary.json', {'schema': 3, 'runs': runs, 'results': results,
                    'repetitions': repetitions, 'qnx_executed': False})
                answer = {'schema': 1, 'status': 'NOT_RUN', 'native_gate_closed': False,
                          'qnx_executed': result.get('qnx_executed', False), 'reason': result['reason']}
                write(out / 'acceptance.json', answer)
                return answer
    write(campaign / 'summary.json', {'schema': 3, 'runs': runs, 'results': results,
                                      'repetitions': repetitions, 'qnx_executed': True})
    gate = assess(campaign)
    write(out / 'native-gate.json', gate)
    answer = {'schema': 1, 'status': 'GATE_NOT_ESTABLISHED',
              'native_gate_closed': gate['native_gate_closed'], 'qnx_executed': True,
              'reduction_complete': False, 'regression_complete': False}
    if not gate['native_gate_closed']:
        write(out / 'acceptance.json', answer)
        return answer
    try:
        witness, record = reduce_actions(NOISY_SCENARIO,
            lambda s,d: run(s, 'ignore_unblock', d, bin_dir), validate,
            'cancel_before_effect', repetitions=2, max_executions=300)
        write(out / 'reduction.json', record)
        if not record['final_reproduces'] or record['deletion_1_minimal'] is not True:
            raise RuntimeError('native reduction or minimality audit is incomplete')
        export = out / 'regressions'; export.mkdir()
        write(export / 'unblock.json', witness)
        write(export / 'suite.json', {'schema': 3, 'adapter': 'qnx-native', 'cases': [
            {'name': 'unblock-before-effect', 'scenario': 'unblock.json',
             'property': 'cancel_before_effect', 'sensitivity_mode': 'ignore_unblock'}]})
        checks = []
        for i in range(5):
            checks.append(regress(export / 'suite.json', out / f'regression-replay-{i}',
                                  bin_dir, sensitivity=True))
        # Deliberately substitute the failing policy into the candidate slot.
        sensitivity = regress(export / 'suite.json', out / 'regressed-candidate',
                              bin_dir, candidate='ignore_unblock')
        good = all(r['passed'] for r in checks)
        bad = (not sensitivity['passed'] and sensitivity['inconclusive'] == 0 and
               sensitivity['qnx_executed'])
        answer.update(reduction_complete=True, regression_complete=good and bad,
                      regressed_candidate_rejected=bad,
                      status='ACCEPTANCE_COMPLETE' if good and bad else 'REGRESSION_NOT_ESTABLISHED')
    except (ValueError, RuntimeError, OSError) as exc:
        answer.update(status='REDUCTION_NOT_ESTABLISHED', error=str(exc))
    write(out / 'acceptance.json', answer)
    return answer


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('accept')
    a.add_argument('--bin', type=Path, required=True); a.add_argument('--out', type=Path, required=True)
    a.add_argument('--repetitions', type=int, default=5)
    r = sub.add_parser('regress')
    r.add_argument('suite', type=Path); r.add_argument('--bin', type=Path, required=True)
    r.add_argument('--out', type=Path, required=True)
    r.add_argument('--candidate', choices=('reference','ignore_unblock'), default='reference')
    r.add_argument('--sensitivity', action='store_true')
    args = p.parse_args()
    if args.command == 'accept':
        result = acceptance(args.bin, args.out, args.repetitions)
        code = 77 if result['status'] == 'NOT_RUN' else 0 if result['status'] == 'ACCEPTANCE_COMPLETE' else 1
    else:
        result = regress(args.suite, args.out, args.bin, args.candidate, args.sensitivity)
        code = 0 if result['passed'] else 77 if not result['qnx_executed'] else 1
    print(json.dumps(result, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
