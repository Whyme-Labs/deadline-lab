"""Re-evaluate native campaign evidence. Linux/synthetic records never close this gate.

Hashes detect accidental corruption, not forged testimony or hostile authors.
This gate covers the bounded native canary, not competition submission readiness.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from .adapters.qnx_native import evaluate


def assess(directory: Path, minimum_repetitions: int = 5) -> dict:
    if type(minimum_repetitions) is not int or minimum_repetitions < 5:
        raise ValueError('native acceptance requires at least five paired repetitions')
    errors: list[str] = []
    checked: list[dict] = []
    identity = None
    try:
        summary = json.loads((directory / 'summary.json').read_text())
        if summary.get('schema') != 3 or summary.get('qnx_executed') is not True:
            raise ValueError('no v0.3 genuine native campaign record')
        repetitions = summary.get('repetitions')
        if type(repetitions) is not int or not minimum_repetitions <= repetitions <= 20:
            raise ValueError('insufficient paired native repetitions')
        runs = summary.get('runs')
        if not isinstance(runs, list) or len(runs) != 2 * repetitions:
            raise ValueError('missing paired native run references')
        expected = {(i, m) for i in range(repetitions) for m in ('reference', 'ignore_unblock')}
        actual = {(r.get('repetition'), r.get('policy')) for r in runs}
        if actual != expected:
            raise ValueError('duplicate or missing native run identities')
        scenarios: dict[int, str] = {}
        for r in runs:
            name = r.get('path')
            canonical = f'{r["repetition"]}-{r["policy"]}'
            if name != canonical or Path(name).name != name:
                raise ValueError('unexpected native run path')
            path = directory / name
            if path.is_symlink() or not path.is_dir():
                raise ValueError('native run directory missing or symlink')
            result = evaluate(path)
            target = json.loads((path / 'target.json').read_text())
            checked.append({'path': name, 'result': result})
            if result['evidence_origin'] != 'native-qnx' or target.get('system') != 'QNX':
                errors.append(name + ': synthetic or non-QNX evidence cannot satisfy native acceptance')
            if target.get('policy') != r['policy']:
                errors.append(name + ': policy mismatch')
            if r['policy'] == 'reference':
                if result['verdict'] != 'PASS' or result['healthy_effects'] != 1:
                    errors.append(name + ': reference did not pass and make healthy progress')
            elif result['verdict'] != 'FAIL' or 'cancel_before_effect' not in result['properties']:
                errors.append(name + ': omitted cancellation control did not expose the intended failure')
            if result['unblock_activations'] < 1:
                errors.append(name + ': requested native condition did not activate')
            current = (target.get('source_set_sha256'), target.get('server_sha256'),
                       target.get('client_sha256'), target.get('abi_sha256'), target.get('machine'))
            if not all(isinstance(v, str) and v for v in current):
                errors.append(name + ': build/target provenance missing')
            if identity is not None and identity != current:
                errors.append(name + ': mixed source, binaries or target architecture')
            identity = current
            scenario = json.dumps(json.loads((path / 'scenario.json').read_text()), sort_keys=True)
            previous = scenarios.setdefault(r['repetition'], scenario)
            if previous != scenario:
                errors.append(name + ': reference and negative control used different scenarios')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        errors.append(str(exc))
    return {'schema': 1, 'gate': 'native-cancellation-canary',
            'status': 'ACCEPTED' if checked and not errors else 'NOT_ESTABLISHED',
            'native_gate_closed': bool(checked) and not errors,
            'runs_rechecked': len(checked), 'errors': errors, 'runs': checked,
            'limits': 'Bounded native canary only. No proof of universal safety, hardware timing, '
                      'evidence authenticity or competition readiness.'}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('campaign', type=Path)
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    result = assess(a.campaign)
    text = json.dumps(result, indent=2) + '\n'
    if a.out:
        with a.out.open('x') as stream:
            stream.write(text)
    print(text, end='')
    return 0 if result['native_gate_closed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
