from __future__ import annotations
import collections
import json
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Any
from .minimize import minimize
from .report import write_report
from .regression import export_suite
from .runner import MODES, ROOT, run_scenario, sha256
from .scenario import generate

TARGET_PROPERTIES = {"omit_epoch": "generation_fence", "omit_expiry": "authorisation_deadline",
                     "omit_cancel": "cancel_acknowledged", "omit_dedupe": "at_most_once"}


def campaign(out: Path, per_split: int = 30, reduce: bool = True,
             binary: Path | None = None, resume: bool = False) -> dict[str, Any]:
    if not 1 <= per_split <= 1000:
        raise ValueError("per-split must be between 1 and 1000")
    out.mkdir(parents=True, exist_ok=resume)
    seeds = [("discovery", 1000+i) for i in range(per_split)] + [("held-out", 100000+i) for i in range(per_split)]
    runs = []
    first_failures = {}
    corpus = []
    for split, seed in seeds:
        scenario = generate(seed)
        corpus.append({"split": split, **scenario})
        for mode in MODES:
            location = out / "runs" / str(seed) / mode
            if resume and location.exists():
                # An interrupted tool session may leave a partial last run. Preserve it.
                if not (location / "manifest.json").exists():
                    archive = location.with_name(location.name + ".interrupted")
                    suffix = 0
                    while archive.exists():
                        suffix += 1
                        archive = location.with_name(location.name + f".interrupted-{suffix}")
                    location.rename(archive)
                    result = run_scenario(scenario, mode, location, binary=binary)
                else:
                    manifest = json.loads((location / "manifest.json").read_text())
                    if any(Path(name).name != name or sha256(location / name) != digest
                           for name, digest in manifest.items()):
                        raise RuntimeError(f"checkpoint integrity mismatch: {location}")
                    if json.loads((location / "scenario.json").read_text()) != scenario:
                        raise RuntimeError("checkpoint scenario mismatch")
                    result = json.loads((location / "result.json").read_text())
                    if result["mode"] != mode or result["worker_sha256"] != sha256(binary or ROOT / "build/dl-worker"):
                        raise RuntimeError("checkpoint executable or mode mismatch")
            else:
                result = run_scenario(scenario, mode, location, binary=binary)
            runs.append({**result, "split": split, "location": str(location.relative_to(out))})
            prop = TARGET_PROPERTIES.get(mode)
            if split == "discovery" and prop and result["verdict"] == "FAIL" and prop in result["properties"]:
                first_failures.setdefault(mode, scenario)
    (out / "corpus.jsonl").write_text("".join(json.dumps(s, sort_keys=True) + "\n" for s in corpus))
    witnesses = []
    if reduce:
        for mode, scenario in first_failures.items():
            witness, details = minimize(scenario, mode, TARGET_PROPERTIES[mode], repetitions=2, binary=binary)
            witness_dir = out / "witnesses" / mode
            witness_dir.mkdir(parents=True)
            (witness_dir / "scenario.json").write_text(json.dumps(witness, indent=2) + "\n")
            observed = {"reference": [], mode: []}
            for replay_mode in ("reference", mode):
                for iteration in range(5):
                    result = run_scenario(witness, replay_mode, witness_dir / f"{replay_mode}-{iteration}", binary=binary)
                    observed[replay_mode].append(result)
            details.update(scenario=witness, reference_replays=5, mutant_replays=5,
                reference_passes=sum(r["verdict"] == "PASS" for r in observed["reference"]),
                mutant_failures=sum(r["verdict"] == "FAIL" and TARGET_PROPERTIES[mode] in r["properties"] for r in observed[mode]),
                replay_inconclusive=sum(r["verdict"] == "INCONCLUSIVE" for rs in observed.values() for r in rs))
            (witness_dir / "reduction.json").write_text(json.dumps(details, indent=2) + "\n")
            witnesses.append(details)
    if witnesses:
        export_suite(witnesses, out / "regressions")
    modes = {}
    for mode in MODES:
        selected = [r for r in runs if r["mode"] == mode]
        counter = collections.Counter(r["verdict"] for r in selected)
        modes[mode] = {"runs": len(selected), "PASS": counter["PASS"], "FAIL": counter["FAIL"],
                       "INCONCLUSIVE": counter["INCONCLUSIVE"], "effects": sum(r["effects"] for r in selected),
                       "healthy_probes": sum(r["probe_effects"] for r in selected)}
    summary = {"schema": 1, "scenarios": len(seeds), "runs": runs, "modes": modes, "witnesses": witnesses,
        "evidence_level": "Linux real subprocesses, synthetic integer plant, deliberate fixture defects",
        "qnx_executed": False, "physical_actuator_tested": False,
        "platform": platform.platform(), "python": platform.python_version(),
        "qcc": shutil.which("qcc"), "qemu": shutil.which("qemu-system-x86_64"),
        "corpus_sha256": sha256(out / "corpus.jsonl"),
        "limitations": ["Seeded defects, not discovered production bugs", "Authored grammar, not coverage-guided fuzzing",
                        "Shared C fixture with two presentation domains, not independently authored integrations",
                        "Command authorisation deadlines, not physical motion deadlines",
                        "Finite executions cannot prove universal safety", "QNX code uncompiled and unexecuted"]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_report(summary, out / "report.html")
    return summary
