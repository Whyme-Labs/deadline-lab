"""Delta debugging against real fixture processes, not a model replay.

A witness is deletion-1-minimal relative to this grammar and requested property,
not globally shortest. Timing can still vary, so each accepted reduction is repeated.
"""
from __future__ import annotations
import math
import tempfile
from pathlib import Path
from typing import Any
from .runner import run_scenario
from .scenario import validate


def minimize(scenario: dict[str, Any], mode: str, property_name: str,
             repetitions: int = 2, binary: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    trials = 0
    invalid = 0
    inconclusive = 0
    cache: dict[str, bool] = {}

    def reproduces(actions: list[dict[str, Any]], use_cache: bool = True) -> bool:
        nonlocal trials, invalid, inconclusive
        candidate = {**scenario, "actions": actions}
        signature = repr(actions)
        if use_cache and signature in cache:
            return cache[signature]
        try:
            validate(candidate)
        except ValueError:
            invalid += 1
            cache[signature] = False
            return False
        reproduced = True
        for _ in range(repetitions):
            with tempfile.TemporaryDirectory(prefix="dl-reduce-") as temp:
                result = run_scenario(candidate, mode, Path(temp) / "run", binary=binary)
            trials += 1
            if result["verdict"] == "INCONCLUSIVE":
                inconclusive += 1
            if result["verdict"] != "FAIL" or property_name not in result["properties"]:
                reproduced = False
                break
        cache[signature] = reproduced
        return reproduced

    actions = list(scenario["actions"])
    if not reproduces(actions, use_cache=False):
        raise RuntimeError("original failure does not reproduce at the required rate")
    granularity = 2
    while len(actions) >= 2:
        chunk = math.ceil(len(actions) / granularity)
        removed = False
        for start in range(0, len(actions), chunk):
            candidate = actions[:start] + actions[start + chunk:]
            if reproduces(candidate):
                actions = candidate
                granularity = max(2, granularity - 1)
                removed = True
                break
        if removed:
            continue
        if granularity >= len(actions):
            break
        granularity = min(len(actions), granularity * 2)
    # Independent one-deletion audit, repeated without memoised timing observations.
    one_minimal = True
    for i in range(len(actions)):
        if reproduces(actions[:i] + actions[i + 1:], use_cache=False):
            one_minimal = False
    final_reproduces = reproduces(actions, use_cache=False)
    witness = {**scenario, "name": f"witness-{mode}-{property_name}", "actions": actions}
    return witness, {"input_actions": len(scenario["actions"]), "witness_actions": len(actions),
        "property": property_name, "mode": mode, "candidate_executions": trials,
        "invalid_candidates": invalid, "inconclusive_candidates": inconclusive,
        "repetitions_per_accepted_candidate": repetitions, "deletion_1_minimal": one_minimal,
        "final_reproduces": final_reproduces,
        "limits": "Grammar-constrained local minimality. No global shortest or exact scheduling claim."}
