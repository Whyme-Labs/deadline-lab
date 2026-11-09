from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path
from .campaign import campaign
from .runner import MODES, ROOT, run_scenario
from .regression import run_suite


def main() -> int:
    parser = argparse.ArgumentParser(prog="deadline-lab")
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("doctor")
    p = subs.add_parser("run")
    p.add_argument("scenario", type=Path)
    p.add_argument("--mode", choices=MODES, default="reference")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--binary", type=Path)
    p.add_argument("--plant", choices=["rotary-axis", "dispenser"], default="rotary-axis")
    p = subs.add_parser("campaign")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--per-split", type=int, default=30)
    p.add_argument("--no-reduce", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--binary", type=Path)
    p = subs.add_parser("regress")
    p.add_argument("suite", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--candidate-mode", choices=MODES, default="reference")
    p.add_argument("--verify-mutants", action="store_true")
    p.add_argument("--binary", type=Path)
    p = subs.add_parser("external-run")
    p.add_argument("scenario", type=Path)
    p.add_argument("--policy", choices=["timeout_only", "deadline", "fenced", "reject_all"], default="fenced")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--nginx", type=Path)
    p = subs.add_parser("external-campaign")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--repetitions", type=int, default=3)
    p.add_argument("--no-reduce", action="store_true")
    p.add_argument("--nginx", type=Path)
    p = subs.add_parser("external-regress")
    p.add_argument("suite", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--candidate-policy", choices=["timeout_only", "deadline", "fenced", "reject_all"], default="fenced")
    p.add_argument("--sensitivity", action="store_true")
    p.add_argument("--nginx", type=Path)
    p = subs.add_parser("external-recheck")
    p.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "doctor":
        print(json.dumps({"python": sys.version, "cc": shutil.which("cc"), "cmake": shutil.which("cmake"),
            "worker_built": (ROOT / "build/dl-worker").is_file(), "qcc": shutil.which("qcc"),
            "qemu_x86_64": shutil.which("qemu-system-x86_64"), "qnx_target_verified": False,
            "qnx_status": "not-tested; SDK detection does not establish a running target"}, indent=2))
        return 0
    try:
        if args.command.startswith("external-"):
            from . import external
            from .adapters import nginx_dav
            if args.command == "external-run":
                result = nginx_dav.run(json.loads(args.scenario.read_text()), args.policy, args.out, args.nginx)
            elif args.command == "external-recheck":
                result = nginx_dav.evaluate(args.directory)
            elif args.command == "external-regress":
                result = external.run_regressions(args.suite, args.out, args.candidate_policy,
                                                 args.sensitivity, args.nginx)
                print(json.dumps({k:v for k,v in result.items() if k != "cases"}, indent=2))
                return 0 if result["passed"] else 2 if result["inconclusive"] else 1
            else:
                result = external.campaign(args.out, args.repetitions, not args.no_reduce, args.nginx)
                print(json.dumps({k:v for k,v in result.items() if k not in {"results", "witnesses", "regression"}}, indent=2))
                counts = result["policies"]
                ok = counts["fenced"]["FAIL"] == 0 and counts["fenced"]["INCONCLUSIVE"] == 0
                ok &= all(c["INCONCLUSIVE"] == 0 for c in counts.values())
                ok &= counts["timeout_only"]["FAIL"] > 0 and counts["deadline"]["FAIL"] > 0
                ok &= result["regression"] is None or result["regression"]["passed"]
                return 0 if ok else 1
            print(json.dumps(result, indent=2))
            return {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2}[result["verdict"]]
        if args.command == "regress":
            result = run_suite(args.suite, args.out, args.candidate_mode, args.verify_mutants, args.binary)
            print(json.dumps({k:v for k,v in result.items() if k != "cases"}, indent=2))
            return 0 if result["passed"] else 2 if result["inconclusive"] else 1
        if args.command == "run":
            result = run_scenario(json.loads(args.scenario.read_text()), args.mode, args.out,
                                  binary=args.binary, plant_kind=args.plant)
            print(json.dumps(result, indent=2))
            return {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2}[result["verdict"]]
        result = campaign(args.out, args.per_split, not args.no_reduce, args.binary, args.resume)
        print(json.dumps({"scenarios": result["scenarios"], "modes": result["modes"],
                         "witnesses": len(result["witnesses"]), "report": str(args.out / 'report.html')}, indent=2))
        reference = result["modes"]["reference"]
        expected = reference["FAIL"] == 0 and reference["INCONCLUSIVE"] == 0
        expected &= all(result["modes"][m]["FAIL"] > 0 for m in MODES if m != "reference")
        expected &= all(s["INCONCLUSIVE"] == 0 for s in result["modes"].values())
        return 0 if expected else 1
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, f"deadline-lab: {exc}\n")

if __name__ == "__main__":
    raise SystemExit(main())
