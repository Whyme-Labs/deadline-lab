"""External-target campaigns and ordinary regression export; no production endpoints."""
from __future__ import annotations
import html
import json
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from .adapters.nginx_dav import POLICIES, evaluate, run, validate
from .reducer import reduce_actions


def scenario(seed: int, family: str) -> dict[str, Any]:
    rng = random.Random(seed)
    values = rng.sample(range(1, 60000), 4)
    actions = [{'op': 'write', 'key': 'setup', 'value': values[0], 'ttl_ms': 2000},
               {'op': 'wait', 'ms': rng.randrange(0, 4)},
               {'op': 'hold', 'key': 'old', 'value': values[1],
                'ttl_ms': rng.choice([20, 30, 40]) if family == 'expiry' else 5000}]
    if family == 'expiry':
        actions += [{'op': 'timeout', 'key': 'old'}]
    actions += [{'op': 'write', 'key': 'new', 'value': values[2], 'ttl_ms': 2000},
                {'op': 'release', 'key': 'old'},
                {'op': 'write', 'key': 'trailing', 'value': values[3], 'ttl_ms': 2000}]
    return {'schema': 2, 'adapter': 'nginx-dav', 'name': f'{family}-{seed}',
            'seed': seed, 'family': family, 'actions': actions}


def _write(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def run_regressions(suite_path: Path, out: Path, candidate: str = 'fenced',
                    sensitivity: bool = False, binary: Path | None = None) -> dict[str, Any]:
    suite = json.loads(suite_path.read_text())
    if suite.get('schema') != 2 or suite.get('adapter') != 'nginx-dav' or candidate not in POLICIES:
        raise ValueError('invalid external suite')
    specs = suite.get('cases')
    if not isinstance(specs, list) or not 1 <= len(specs) <= 16:
        raise ValueError('invalid suite cases')
    root = suite_path.resolve().parent
    loaded = []
    for spec in specs:
        relative = spec.get('scenario')
        if not isinstance(relative, str) or Path(relative).name != relative:
            raise ValueError('suite scenario must be in the suite directory')
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError('invalid scenario path')
        s = json.loads(path.read_text()); validate(s)
        if spec.get('sensitivity_policy') not in POLICIES or not isinstance(spec.get('property'), str):
            raise ValueError('invalid sensitivity control')
        loaded.append((spec, s))
    out.mkdir(parents=True, exist_ok=False)
    cases = []
    for i, (spec, s) in enumerate(loaded):
        choices = [(candidate, 'candidate')]
        if sensitivity:
            choices.append((spec['sensitivity_policy'], 'sensitivity'))
        for policy, purpose in choices:
            result = run(s, policy, out / f'{i}-{purpose}', binary)
            ok = result['verdict'] == 'PASS' if purpose == 'candidate' else (
                result['verdict'] == 'FAIL' and spec['property'] in result['properties'])
            cases.append({'name': spec['name'], 'purpose': purpose, 'policy': policy,
                          'expected_outcome_observed': ok, 'result': result})
    failed = sum(not c['expected_outcome_observed'] for c in cases)
    inconclusive = sum(c['result']['verdict'] == 'INCONCLUSIVE' for c in cases)
    summary = {'schema': 2, 'checks': len(cases), 'failed_expectations': failed,
               'inconclusive': inconclusive, 'passed': failed == 0, 'cases': cases,
               'qnx_executed': False}
    _write(out / 'summary.json', summary)
    xml = ET.Element('testsuite', name='deadline-lab.external', tests=str(len(cases)),
                     failures=str(failed - inconclusive), errors=str(inconclusive))
    for c in cases:
        node = ET.SubElement(xml, 'testcase', classname='deadline_lab.nginx',
                             name=c['name'] + '.' + c['purpose'])
        if not c['expected_outcome_observed']:
            ET.SubElement(node, 'error' if c['result']['verdict'] == 'INCONCLUSIVE' else 'failure',
                          message='Expected outcome not observed').text = json.dumps(c['result'])
        ET.SubElement(node, 'system-out').text = json.dumps(c['result'])
    ET.ElementTree(xml).write(out / 'junit.xml', encoding='utf-8', xml_declaration=True)
    return summary


def campaign(out: Path, repetitions: int = 3, reduce: bool = True,
             binary: Path | None = None) -> dict[str, Any]:
    if not 1 <= repetitions <= 20:
        raise ValueError('repetitions must be 1..20')
    out.mkdir(parents=True, exist_ok=False)
    results, inputs = [], []
    stats = {p: {'PASS': 0, 'FAIL': 0, 'INCONCLUSIVE': 0} for p in POLICIES}
    for family in ('expiry', 'reordering'):
        for repeat in range(repetitions):
            s = scenario(2000 + repeat, family); inputs.append(s)
            for p in POLICIES:
                path = out / 'runs' / family / str(repeat) / p
                r = run(s, p, path, binary)
                stats[p][r['verdict']] += 1
                results.append({'family': family, 'repeat': repeat, 'result': r,
                                'path': str(path.relative_to(out))})
    # A committed request with a lost response is not rolled back by timing out.
    ack_case = {'schema': 2, 'adapter': 'nginx-dav', 'name': 'ack-loss-is-unknown',
                'actions': [{'op': 'lost_ack', 'key': 'write', 'value': 321, 'ttl_ms': 100}]}
    ambiguous = []
    for p in POLICIES:
        r = run(ack_case, p, out / 'ack-loss' / p, binary)
        ambiguous.append(r)
    witnesses = []
    if reduce:
        export = out / 'regressions'; export.mkdir()
        for family, policy, prop in [('expiry', 'timeout_only', 'expired_dispatch_effect'),
                                     ('reordering', 'deadline', 'superseded_effect')]:
            s = next(s for s in inputs if s['family'] == family)
            witness, record = reduce_actions(s, lambda c, p: run(c, policy, p, binary),
                                              validate, prop, repetitions=2)
            _write(export / (family + '.json'), witness)
            replay = []
            for i in range(5):
                for p in (policy, 'fenced'):
                    r = run(witness, p, out / 'replays' / family / str(i) / p, binary)
                    replay.append({'policy': p, 'result': r})
            witnesses.append({'family': family, 'policy': policy, 'property': prop,
                              'scenario': witness, 'reduction': record, 'replays': replay})
        suite = {'schema': 2, 'adapter': 'nginx-dav', 'cases': [
            {'name': w['family'], 'scenario': w['family'] + '.json',
             'property': w['property'], 'sensitivity_policy': w['policy']} for w in witnesses]}
        _write(export / 'suite.json', suite)
        regression = run_regressions(export / 'suite.json', out / 'regression-check',
                                     sensitivity=True, binary=binary)
    else:
        regression = None
    _write(out / 'inputs.json', inputs)
    summary = {'schema': 2, 'adapter': 'nginx-dav', 'scenario_runs': len(results),
        'policies': stats, 'results': results, 'ack_loss_controls': ambiguous,
        'witnesses': witnesses, 'regression': regression, 'qnx_executed': False,
        'claims': 'Independently authored unmodified nginx executed on Linux. '
                  'Gateway code, fault hooks and application requirements are ours. '
                  'No nginx defect, QNX execution or real actuator performance is claimed.'}
    _write(out / 'summary.json', summary)
    render(summary, out / 'report.html')
    return summary


def render(summary: dict[str, Any], path: Path) -> None:
    rows = ''.join('<tr><td>' + html.escape(p) + '</td>' + ''.join(
        '<td>' + str(d[k]) + '</td>' for k in ('PASS', 'FAIL', 'INCONCLUSIVE')) + '</tr>'
        for p, d in summary['policies'].items())
    witness_html = ''
    for w in summary['witnesses']:
        rr = w['reduction']
        witness_html += (f'<h3>{html.escape(w["property"])}</h3>'
            f'<p>{rr["input_actions"]} actions reduced to {rr["witness_actions"]}. '
            f'Deletion-1-minimal: {rr["deletion_1_minimal"]}. '
            'Five recorded replays per policy.</p><pre>' +
            html.escape(json.dumps(w['scenario']['actions'], indent=2)) + '</pre>')
    path.write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Deadline Lab | Independent target checkpoint</title>
<style>body{font:17px/1.6 system-ui;max-width:960px;margin:40px auto;padding:0 24px;color:#16222a;background:#f7fafb}
h1{font-size:38px;line-height:1.15}h2{margin-top:40px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #ccd6dc}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#e8eff3;padding:18px;border-radius:8px}.note{border-left:4px solid #b16612;padding:12px 20px;background:#fff4e4}small{color:#4b5b66}</style>
<header><small>DEADLINE LAB / v0.2.0 / 9 November 2026</small>
<h1>A timeout did not cancel the write.</h1>
<p>Real HTTP requests. An unmodified nginx server. Filesystem evidence.</p></header>
<p class="note">Linux evidence only. QNX execution remains blocked. This is an application-contract demonstration, not a newly discovered nginx bug or a physical actuator test.</p>
<h2>What the test exposes</h2><p>A held old request can survive a client timeout and overwrite a newer value. An expiry guard stops late dispatch. It does not stop reordering while both requests remain valid. A sequence fence addresses that separate failure in this test setup.</p>
<h2>Recorded campaign</h2><table><thead><tr><th>Gateway policy</th><th>Pass</th><th>Fail</th><th>Inconclusive</th></tr></thead><tbody>''' + rows + '''</tbody></table>
<p>These are authored policy comparisons, not independent products or detection-accuracy estimates. Each run includes a healthy write so rejecting everything cannot pass.</p>
<h2>Reduced regression cases</h2>''' + witness_html + '''
<h2>Evidence boundaries</h2><p>The observer reads the file nginx wrote instead of trusting a gateway success response. A lost acknowledgement is recorded as an unknown outcome until state is observed. The fence protects admission ordering at this one serial gateway; it does not establish durability, across-reboot exactly-once effects, or a hard backend commit deadline.</p>
<p>Raw scenarios, file snapshots, server configuration, version, binary hashes, logs and integrity manifests are in the accompanying project bundle.</p>
</html>''')
