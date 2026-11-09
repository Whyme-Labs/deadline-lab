"""Check effect evidence independently of the C controller's accept/reject decisions."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
from typing import Any
from .trace import read_trace


def evaluate(trace_path: Path, commands: dict[int, dict[str, Any]],
             attempts: dict[int, dict[str, Any]], probe_id: int,
             infrastructure_error: str | None = None) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    evidence_errors = []
    effects = []
    records = []
    if infrastructure_error:
        evidence_errors.append(infrastructure_error)
    try:
        records = read_trace(trace_path)
        effects = records[1:-1]
    except (ValueError, KeyError, TypeError, OSError) as exc:
        evidence_errors.append(str(exc))
    seen: Counter[int] = Counter()
    state = 0
    for effect in effects:
        command_id, attempt_id = effect["command_id"], effect["attempt"]
        c, attempt = commands.get(command_id), attempts.get(attempt_id)
        if c is None or attempt is None or attempt["command_id"] != command_id:
            evidence_errors.append("effect cannot be associated with an issued command and attempt")
            continue
        if effect["worker_epoch"] != attempt["worker_epoch"] or effect["request_epoch"] != c["epoch"]:
            evidence_errors.append("effect provenance mismatch")
        if effect["commit_ns"] < attempt["started_ns"] or effect["commit_ns"] > effect["observed_ns"]:
            evidence_errors.append("effect timestamp provenance mismatch")
        if effect["delta"] != c["delta"]:
            violations.append({"property": "payload_integrity", "command_id": command_id, "attempt": attempt_id})
        state += effect["delta"]
        if effect["state_before"] != state - effect["delta"] or effect["state_after"] != state:
            evidence_errors.append("virtual plant state is inconsistent")
        checks = {
            "generation_fence": c["epoch"] == attempt["worker_epoch"],
            "authorisation_deadline": c["issued_ns"] <= effect["commit_ns"] < c["expires_ns"],
            "cancel_acknowledged": not attempt["cancelled_before"],
            "at_most_once": seen[command_id] == 0,
        }
        for prop, passed in checks.items():
            if not passed:
                violations.append({"property": prop, "command_id": command_id, "attempt": attempt_id,
                                   "effect_sequence": effect["seq"]})
        seen[command_id] += 1
    if records and records[-1]["final_state"] != state:
        evidence_errors.append("final plant state mismatch")
    for attempt_id, attempt in attempts.items():
        matching = [e for e in effects if e["attempt"] == attempt_id]
        if attempt.get("response") == "apply" and len(matching) != 1:
            evidence_errors.append("acknowledged effect has missing or duplicated evidence")
    probe_count = seen[probe_id]
    if probe_count != 1:
        violations.append({"property": "healthy_progress", "command_id": probe_id,
                           "expected_effects": 1, "actual_effects": probe_count})
    return {
        "verdict": "INCONCLUSIVE" if evidence_errors else "FAIL" if violations else "PASS",
        "violations": violations, "evidence_errors": sorted(set(evidence_errors)),
        "effects": len(effects), "probe_effects": probe_count, "final_virtual_state": state,
        "properties": sorted({v["property"] for v in violations}),
    }
