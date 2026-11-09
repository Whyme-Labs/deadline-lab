"""Run only locally spawned fixture processes. Never signals a supplied PID."""
from __future__ import annotations
import hashlib
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from .oracle import evaluate
from .scenario import validate

ROOT = Path(__file__).resolve().parents[1]
MODES = ("reference", "omit_epoch", "omit_expiry", "omit_cancel", "omit_dedupe", "reject_all")


class Actor:
    def __init__(self, binary: Path, mode: str, epoch: int, effect_fd: int, stderr_path: Path):
        self.stderr = stderr_path.open("ab")
        self.process = subprocess.Popen([str(binary), mode, str(epoch), str(effect_fd)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            pass_fds=(effect_fd,), bufsize=0, start_new_session=True)
        self.buffer = b""
        self.stopped = False
        try:
            hello = self.read_line(2.0)
            if hello != f"READY {epoch} {self.process.pid}":
                raise RuntimeError(f"worker startup failed: {hello!r}")
        except BaseException:
            self.close()
            raise

    def read_line(self, timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        assert self.process.stdout is not None
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            ready, _, _ = select.select([self.process.stdout.fileno()], [], [], remaining)
            if not ready:
                return None
            data = os.read(self.process.stdout.fileno(), 4096)
            if not data:
                raise RuntimeError(f"worker EOF, exit={self.process.poll()}")
            self.buffer += data
            if len(self.buffer) > 4096:
                raise RuntimeError("oversized worker response")
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line.decode("ascii")

    def request(self, wire: str, lost_ack: bool = False) -> str:
        if self.process.poll() is not None:
            raise RuntimeError("request to exited worker")
        assert self.process.stdin is not None
        self.process.stdin.write(wire.encode("ascii") + b"\n")
        response = self.read_line(0.006 if lost_ack else 2.0)
        if lost_ack:
            if response is not None:
                raise RuntimeError("ack-loss hook unexpectedly replied")
            return "unknown_timeout"
        if response is None or not response.startswith("R "):
            raise RuntimeError(f"invalid/missing response: {response!r}")
        return response[2:]

    def pause(self, ms: int) -> None:
        if self.process.poll() is not None:
            raise RuntimeError("cannot pause exited worker")
        self.process.send_signal(signal.SIGSTOP)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            pid, status = os.waitpid(self.process.pid, os.WUNTRACED | os.WNOHANG)
            if pid and os.WIFSTOPPED(status):
                self.stopped = True
                break
            time.sleep(0.001)
        else:
            raise RuntimeError("SIGSTOP was not observed")
        time.sleep(ms / 1000)
        self.process.send_signal(signal.SIGCONT)
        self.stopped = False
        if self.request("H") != "ok":
            raise RuntimeError("worker failed after resume")

    def close(self, hard: bool = False) -> None:
        p = self.process
        try:
            if p.poll() is None:
                if self.stopped:
                    p.send_signal(signal.SIGCONT)
                    self.stopped = False
                if hard:
                    p.kill()
                else:
                    try:
                        self.request("Q")
                    except (OSError, RuntimeError):
                        p.kill()
                try:
                    p.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=2)
        finally:
            for stream in (p.stdin, p.stdout):
                if stream:
                    stream.close()
            self.stderr.close()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_scenario(scenario: dict[str, Any], mode: str, out: Path,
                 binary: Path | None = None, plant_kind: str = "rotary-axis") -> dict[str, Any]:
    validate(scenario)
    if mode not in MODES:
        raise ValueError("unknown mode")
    if plant_kind not in {"rotary-axis", "dispenser"}:
        raise ValueError("unknown virtual plant")
    binary = (binary or ROOT / "build/dl-worker").resolve()
    if not binary.is_file():
        raise FileNotFoundError(f"build the local C worker first: {binary}")
    out.mkdir(parents=True, exist_ok=False)
    (out / "scenario.json").write_text(json.dumps(scenario, indent=2) + "\n")
    started_ns = time.monotonic_ns()
    commands: dict[int, dict[str, Any]] = {}
    attempts: dict[int, dict[str, Any]] = {}
    keys: dict[str, int] = {}
    cancelled: set[int] = set()
    journal: list[dict[str, Any]] = []
    epoch = 1
    next_id = 1
    attempt_counter = 0
    actor = None
    plant = None
    error = None
    probe_id = -1
    read_fd, write_fd = os.pipe()
    plant_stderr = (out / "plant.stderr").open("wb")

    def record(kind: str, **kwargs: Any) -> None:
        journal.append({"seq": len(journal), "kind": kind, "monotonic_ns": time.monotonic_ns(), **kwargs})

    def prepare(cid: int) -> str:
        c = commands[cid]
        assert actor is not None
        return actor.request(f"P {cid} {c['epoch']} {c['issued_ns']} {c['expires_ns']} {c['delta']}")

    def commit(cid: int, lost_ack: bool = False) -> str:
        nonlocal attempt_counter
        assert actor is not None
        attempt_counter += 1
        attempt = {"command_id": cid, "worker_epoch": epoch, "cancelled_before": cid in cancelled,
                   "started_ns": time.monotonic_ns(), "lost_ack": lost_ack}
        attempts[attempt_counter] = attempt
        response = actor.request(f"{'L' if lost_ack else 'C'} {cid} {attempt_counter}", lost_ack=lost_ack)
        attempt.update(response=response, completed_ns=time.monotonic_ns())
        return response

    try:
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        plant = subprocess.Popen([sys.executable, "-S", "-m", "deadline_lab.plant", "--fd", str(read_fd),
            "--out", str(out / "effects.jsonl"), "--kind", plant_kind],
            stdout=subprocess.PIPE, stderr=plant_stderr, pass_fds=(read_fd,), env=env, bufsize=0)
        os.close(read_fd)
        read_fd = -1
        assert plant.stdout is not None
        ready, _, _ = select.select([plant.stdout], [], [], 2)
        if not ready or plant.stdout.readline() != b"READY\n":
            raise RuntimeError("plant startup failed")
        actor = Actor(binary, mode, epoch, write_fd, out / "worker.stderr")
        record("boot", epoch=epoch, pid=actor.process.pid)
        for index, action in enumerate(scenario["actions"]):
            if time.monotonic_ns() - started_ns > 15_000_000_000:
                raise RuntimeError("scenario execution budget exceeded")
            op = action["op"]
            response = None
            if op == "mint":
                cid = next_id
                next_id += 1
                now = time.monotonic_ns()
                keys[action["key"]] = cid
                commands[cid] = {"id": cid, "epoch": epoch, "issued_ns": now,
                    "expires_ns": now + action["ttl_ms"] * 1_000_000, "delta": action["delta"]}
            elif op == "prepare":
                response = prepare(keys[action["key"]])
            elif op in {"commit", "lost_ack"}:
                response = commit(keys[action["key"]], lost_ack=op == "lost_ack")
            elif op == "cancel":
                cid = keys[action["key"]]
                response = actor.request(f"X {cid}")
                if response == "ok":
                    cancelled.add(cid)
            elif op == "abandon":
                response = actor.request("A")
            elif op == "restart":
                old_pid = actor.process.pid
                actor.close(hard=True)
                record("killed", pid=old_pid, returncode=actor.process.returncode, epoch=epoch)
                epoch += 1
                actor = Actor(binary, mode, epoch, write_fd, out / "worker.stderr")
                record("boot", epoch=epoch, pid=actor.process.pid)
            elif op == "pause":
                actor.pause(action["ms"])
                response = "stop_observed_and_resumed"
            elif op == "wait":
                time.sleep(action["ms"] / 1000)
            record("action", index=index, action=action, response=response, epoch=epoch)
        # A healthy, fresh command is mandatory, even for a reduced failure witness.
        actor.request("A")
        probe_id = next_id
        now = time.monotonic_ns()
        commands[probe_id] = {"id": probe_id, "epoch": epoch, "issued_ns": now,
                            "expires_ns": now + 10_000_000_000, "delta": 1}
        record("healthy_probe", command_id=probe_id, prepared=prepare(probe_id), response=commit(probe_id))
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        error = f"{type(exc).__name__}: {exc}"
        record("infrastructure_error", error=error)
    finally:
        if actor is not None:
            actor.close()
            if actor.process.returncode not in {0, -signal.SIGKILL} and error is None:
                error = f"worker exited {actor.process.returncode}"
        if read_fd >= 0:
            os.close(read_fd)
        os.close(write_fd)
        if plant is not None:
            try:
                plant.wait(timeout=3)
            except subprocess.TimeoutExpired:
                plant.kill()
                plant.wait(timeout=2)
                error = error or "plant shutdown timeout"
            if plant.returncode != 0:
                error = error or f"plant exited {plant.returncode}"
            if plant.stdout:
                plant.stdout.close()
        plant_stderr.close()
    ended_ns = time.monotonic_ns()
    (out / "host-events.jsonl").write_text("".join(json.dumps(e, sort_keys=True) + "\n" for e in journal))
    inputs = {"commands": commands, "attempts": attempts, "probe_id": probe_id}
    (out / "oracle-inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    result = evaluate(out / "effects.jsonl", commands, attempts, probe_id, error)
    result.update(schema=1, mode=mode, name=scenario.get("name", "unnamed"),
                  seed=scenario.get("seed"), action_count=len(scenario["actions"]),
                  evidence_level="linux-real-processes/synthetic-plant", qnx_executed=False,
                  elapsed_ms=round((ended_ns - started_ns) / 1_000_000, 3), plant=plant_kind,
                  worker_sha256=sha256(binary), physical_actuator_tested=False)
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    manifest = {p.name: sha256(p) for p in sorted(out.iterdir()) if p.is_file()}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return result
