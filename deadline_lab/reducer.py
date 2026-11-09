"""Adapter-neutral, repeated deletion reduction.

The runner must create a fresh isolated target per call. INCONCLUSIVE never counts
as reproduction. This establishes only deletion-1-minimality under the validator.
"""
from __future__ import annotations
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
    if not 1 <= repetitions <= 10 or max_executions < repetitions:
        raise ValueError('invalid reduction budget')
    trials = invalid = inconclusive = 0
    cache: dict[str, bool] = {}

    def reproduces(actions: list[dict[str, Any]], cached: bool = True) -> bool:
        nonlocal trials, invalid, inconclusive
        candidate = {**scenario, 'actions': actions}
        signature = json.dumps(actions, sort_keys=True, allow_nan=False)
        if cached and signature in cache:
            return cache[signature]
        try:
            validator(candidate)
        except (ValueError, TypeError, KeyError):
            invalid += 1
            cache[signature] = False
            return False
        success = True
        for _ in range(repetitions):
            if trials >= max_executions:
                raise RuntimeError('reduction execution budget exhausted; no minimality claim')
            with tempfile.TemporaryDirectory(prefix='dl-adapter-reduce-') as temp:
                result = runner(candidate, Path(temp) / 'run')
            trials += 1
            if result.get('verdict') == 'INCONCLUSIVE':
                inconclusive += 1
            if result.get('verdict') != 'FAIL' or property_name not in result.get('properties', []):
                success = False
                break
        cache[signature] = success
        return success

    actions = list(scenario['actions'])
    if not reproduces(actions, cached=False):
        raise RuntimeError('original failure does not reproduce at the required rate')
    n = 2
    while len(actions) >= 2:
        size = math.ceil(len(actions) / n)
        reduced = False
        for start in range(0, len(actions), size):
            candidate = actions[:start] + actions[start + size:]
            if reproduces(candidate):
                actions = candidate
                n = max(2, n - 1)
                reduced = True
                break
        if reduced:
            continue
        if n >= len(actions):
            break
        n = min(len(actions), n * 2)
    minimal = True
    for i in range(len(actions)):
        if reproduces(actions[:i] + actions[i + 1:], cached=False):
            minimal = False
    final = reproduces(actions, cached=False)
    return {**scenario, 'actions': actions}, {
        'input_actions': len(scenario['actions']), 'witness_actions': len(actions),
        'property': property_name, 'candidate_executions': trials,
        'invalid_candidates': invalid, 'inconclusive_candidates': inconclusive,
        'repetitions_per_accepted_candidate': repetitions,
        'deletion_1_minimal': minimal, 'final_reproduces': final,
        'limits': 'Grammar-constrained deletion-1-minimality; not globally shortest or exhaustive.'}
