"""A chained trace detects accidental truncation/reordering/modification, not forgery."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


class TraceWriter:
    def __init__(self, path: Path):
        self.file = path.open("wb")
        self.seq = 0
        self.previous = "0" * 64

    def write(self, kind: str, **payload: Any) -> None:
        record = {"schema": 1, "seq": self.seq, "prev": self.previous, "kind": kind, **payload}
        digest = hashlib.sha256(canonical(record)).hexdigest()
        self.file.write(canonical({**record, "hash": digest}) + b"\n")
        self.file.flush()
        self.seq += 1
        self.previous = digest

    def close(self) -> None:
        self.file.close()


def read_trace(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if not raw or not raw.endswith(b"\n"):
        raise ValueError("missing or partial trace")
    records = []
    previous = "0" * 64
    for seq, line in enumerate(raw.splitlines()):
        record = json.loads(line)
        digest = record.pop("hash")
        if record.get("seq") != seq or record.get("prev") != previous or record.get("schema") != 1:
            raise ValueError("trace sequence/schema mismatch")
        if hashlib.sha256(canonical(record)).hexdigest() != digest:
            raise ValueError("trace digest mismatch")
        previous = digest
        records.append({**record, "hash": digest})
    if len(records) < 2 or records[0].get("kind") != "start":
        raise ValueError("trace header missing")
    if records[-1].get("kind") != "end" or not records[-1].get("complete"):
        raise ValueError("trace completion missing")
    if any(r["kind"] != "effect" for r in records[1:-1]):
        raise ValueError("unexpected trace event")
    if records[-1].get("effect_count") != len(records) - 2:
        raise ValueError("effect count mismatch")
    return records
