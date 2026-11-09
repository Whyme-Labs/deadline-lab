"""Bounded scenario grammar. No shell commands, external PIDs or network targets."""
from __future__ import annotations
import random
from typing import Any

OPS = {"mint", "prepare", "commit", "cancel", "lost_ack", "restart", "pause", "wait", "abandon"}
REF_OPS = {"prepare", "commit", "cancel", "lost_ack"}


def validate(scenario: dict[str, Any]) -> None:
    if scenario.get("schema") != 1 or not isinstance(scenario.get("actions"), list):
        raise ValueError("scenario requires schema=1 and actions")
    actions = scenario["actions"]
    if len(actions) > 200:
        raise ValueError("at most 200 actions")
    minted = set()
    duration = 0
    restarts = 0
    for action in actions:
        if not isinstance(action, dict) or action.get("op") not in OPS:
            raise ValueError("unsupported action")
        op = action["op"]
        permitted = {"op"}
        if op == "mint":
            permitted |= {"key", "ttl_ms", "delta"}
            key = action.get("key")
            if not isinstance(key, str) or not key.isalnum() or len(key) > 24 or key in minted:
                raise ValueError("mint keys must be unique short alphanumeric strings")
            for field, minimum, maximum in [("ttl_ms", 1, 60000), ("delta", -1000000, 1000000)]:
                value = action.get(field)
                if type(value) is not int or not minimum <= value <= maximum:
                    raise ValueError(f"invalid {field}")
            if action["delta"] == 0:
                raise ValueError("delta cannot be zero")
            minted.add(key)
        elif op in REF_OPS:
            permitted.add("key")
            if action.get("key") not in minted:
                raise ValueError("command reference is not minted")
        elif op in {"pause", "wait"}:
            permitted.add("ms")
            ms = action.get("ms")
            if type(ms) is not int or not 1 <= ms <= 100:
                raise ValueError("wait/pause must be between 1 and 100 ms")
            duration += ms
        elif op == "restart":
            restarts += 1
        if set(action) - permitted:
            raise ValueError("unknown action field")
    if duration > 1500 or restarts > 16:
        raise ValueError("scenario exceeds bounded fault budget")


def generate(seed: int, transactions: int = 6) -> dict[str, Any]:
    """Mode-blind grammar generation. Fault families are authored, their combinations are not."""
    rng = random.Random(seed)
    actions: list[dict[str, Any]] = []
    previous: list[str] = []
    for i in range(transactions):
        key = f"c{i}"
        ttl = rng.choice([8, 5000, 5000])
        actions += [{"op": "abandon"}, {"op": "mint", "key": key, "ttl_ms": ttl,
                     "delta": rng.choice([-5, -2, 1, 3, 7])}, {"op": "prepare", "key": key}]
        choices = rng.sample(["restart", "cancel", "pause", "wait", "abandon"], rng.randrange(4))
        for fault in choices:
            if fault in {"pause", "wait"}:
                actions.append({"op": fault, "ms": rng.choice([12, 16, 24])})
            elif fault == "cancel":
                actions.append({"op": "cancel", "key": key})
            else:
                actions.append({"op": fault})
        # Delivery is independent of preparation before a fault. Old command bytes are retained.
        actions.append({"op": "prepare", "key": key})
        actions.append({"op": rng.choice(["commit", "commit", "lost_ack"]), "key": key})
        if rng.random() < 0.55:
            actions += [{"op": "prepare", "key": key}, {"op": "commit", "key": key}]
        if previous and rng.random() < 0.4:
            old = rng.choice(previous)
            actions += [{"op": "abandon"}, {"op": "prepare", "key": old}, {"op": "commit", "key": old}]
        previous.append(key)
    result = {"schema": 1, "name": f"generated-{seed}", "seed": seed, "actions": actions}
    validate(result)
    return result
