"""Backwards-compatible C-fixture adapter for the general deletion reducer."""
from pathlib import Path
from typing import Any
from .runner import run_scenario
from .scenario import validate
from .reducer import reduce_actions


def minimize(scenario: dict[str, Any], mode: str, property_name: str,
             repetitions: int = 2, binary: Path | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    witness, record = reduce_actions(scenario,
        lambda candidate, path: run_scenario(candidate, mode, path, binary=binary),
        validate, property_name, repetitions)
    witness['name'] = f'witness-{mode}-{property_name}'
    record['mode'] = mode
    return witness, record
