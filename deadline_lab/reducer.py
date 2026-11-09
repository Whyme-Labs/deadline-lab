"""Adapter-neutral repeated deletion reduction with explicit unknown outcomes.

The runner creates an isolated target per call. A failure witness requires every
repetition to reproduce the named property. INCONCLUSIVE and NOT_RUN may not be
used as evidence that a one-deletion neighbour is non-failing.
"""
from __future__ import annotations
import hashlib
import json
import math
import tempfile
from pathlib import Path
from typing import Any, Callable

Runner = Callable[[dict[str, Any], Path], dict[str, Any]]
Validator = Callable[[dict[str, Any]], None]


def reduce_actions(scenario: dict[str, Any], runner: Runner, validator: Validator,
                   property_name: str, repetitions: int = 2,
                   max_executions: int = 500) -> tuple[dict[str, Any], dict[str, Any]]:
    if (type(repetitions) is not int or type(max_executions) is not int or
            not 1 <= repetitions <= 10 or max_executions < repetitions or
            not isinstance(property_name, str) or not property_name):
        raise ValueError('invalid reduction budget or property')
    validator(scenario)
    trials = invalid = inconclusive = not_run = 0
    cache: dict[str, str] = {}
    observations: list[dict[str, Any]] = []

    def classify(actions: list[dict[str, Any]], cached: bool = True) -> str:
        nonlocal trials, invalid, inconclusive, not_run
        candidate = {**scenario, 'actions': actions}
        signature = json.dumps(actions, sort_keys=True, allow_nan=False)
        if cached and signature in cache:
            return cache[signature]
        record: dict[str, Any] = {'actions': len(actions),
            'sha256': hashlib.sha256(signature.encode()).hexdigest(), 'runs': []}
        try:
            validator(candidate)
        except (ValueError, TypeError, KeyError):
            invalid += 1
            record['outcome'] = 'INVALID'
            observations.append(record)
            cache[signature] = 'INVALID'
            return 'INVALID'
        reproduced = 0
        unknown = False
        for _ in range(repetitions):
            if trials >= max_executions:
                raise RuntimeError('reduction execution budget exhausted; no minimality claim')
            with tempfile.TemporaryDirectory(prefix='dl-adapter-reduce-') as temp:
                result = runner(candidate, Path(temp) / 'run')
            trials += 1
            verdict = result.get('verdict')
            properties = result.get('properties', [])
            record['runs'].append({'verdict': verdict, 'properties': properties})
            if verdict not in {'PASS', 'FAIL'}:
                unknown = True
                if verdict == 'NOT_RUN':
                    not_run += 1
                else:
                    inconclusive += 1
            elif verdict == 'FAIL' and property_name in properties:
                reproduced += 1
        outcome = ('INCONCLUSIVE' if unknown else
                   'REPRODUCED' if reproduced == repetitions else 'NOT_REPRODUCED')
        record['outcome'] = outcome
        observations.append(record)
        cache[signature] = outcome
        return outcome

    actions = list(scenario['actions'])
    if classify(actions, cached=False) != 'REPRODUCED':
        raise RuntimeError('original failure does not reproduce at the required rate')
    n = 2
    while len(actions) >= 2:
        size = math.ceil(len(actions) / n)
        reduced = False
        for start in range(0, len(actions), size):
            candidate = actions[:start] + actions[start + size:]
            if classify(candidate) == 'REPRODUCED':
                actions = candidate
                n = max(2, n - 1)
                reduced = True
                break
        if reduced:
            continue
        if n >= len(actions):
            break
        n = min(len(actions), n * 2)
    audit = []
    for i in range(len(actions)):
        audit.append({'removed_index': i,
                      'outcome': classify(actions[:i] + actions[i + 1:], cached=False)})
    final = classify(actions, cached=False) == 'REPRODUCED'
    unknown_audit = any(a['outcome'] == 'INCONCLUSIVE' for a in audit)
    removable = any(a['outcome'] == 'REPRODUCED' for a in audit)
    minimal: bool | None = (False if removable or not final else
                            None if unknown_audit else True)
    return {**scenario, 'actions': actions}, {
        'input_actions': len(scenario['actions']), 'witness_actions': len(actions),
        'property': property_name, 'candidate_executions': trials,
        'invalid_candidates': invalid, 'inconclusive_candidates': inconclusive,
        'not_run_candidates': not_run,
        'repetitions_per_accepted_candidate': repetitions,
        'deletion_1_minimal': minimal,
        'minimality_status': 'INCONCLUSIVE' if minimal is None else 'SUPPORTED' if minimal else 'NOT_ESTABLISHED',
        'deletion_audit': audit, 'observations': observations, 'final_reproduces': final,
        'limits': 'Empirical grammar-constrained deletion-1-minimality at the declared repetitions. '
                  'Not globally shortest, exhaustive, deterministic-schedule proof or statistical certainty.'}
