"""Separate virtual plant process. It has no knowledge of controller mutations.

Effects update an integer state. This is not an actuator dynamics model. Authorisation
and observation timestamps are distinct, and no physical deadline is inferred.
"""
from __future__ import annotations
import argparse
import os
import time
from pathlib import Path
from .trace import TraceWriter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--kind", choices=["rotary-axis", "dispenser"], default="rotary-axis")
    args = parser.parse_args()
    trace = TraceWriter(args.out)
    state = 0
    count = 0
    complete = True
    error = None
    trace.write("start", plant=args.kind, pid=os.getpid(), monotonic_ns=time.monotonic_ns())
    print("READY", flush=True)
    try:
        with os.fdopen(args.fd, "rb", buffering=0) as stream:
            for line in iter(lambda: stream.readline(257), b""):
                if len(line) > 256:
                    raise ValueError("oversized effect frame")
                tokens = line.decode("ascii").split()
                if len(tokens) != 7 or tokens[0] != "E" or not line.endswith(b"\n"):
                    raise ValueError("malformed effect frame")
                command_id, request_epoch, worker_epoch, attempt, commit_ns, delta = map(int, tokens[1:])
                if not all(v > 0 for v in (command_id, request_epoch, worker_epoch, attempt, commit_ns)):
                    raise ValueError("invalid effect metadata")
                if delta == 0 or abs(delta) > 1000000:
                    raise ValueError("invalid effect amount")
                observed_ns = time.monotonic_ns()
                previous = state
                state += delta
                count += 1
                trace.write("effect", command_id=command_id, request_epoch=request_epoch,
                            worker_epoch=worker_epoch, attempt=attempt, commit_ns=commit_ns,
                            observed_ns=observed_ns, delta=delta, state_before=previous, state_after=state)
    except (ValueError, OSError, UnicodeError) as exc:
        complete, error = False, str(exc)
    trace.write("end", complete=complete, error=error, effect_count=count, final_state=state,
                monotonic_ns=time.monotonic_ns())
    trace.close()
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
