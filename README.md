# Deadline Lab

A recovery bug-to-regression workbench. Generate a failure sequence, observe what the target actually does, reduce the sequence, and export a test a developer can keep.

**v0.1.0 is a local engineering prototype.** The C controller, process fault runner, virtual plant, independent checker, reducer and regression exporter have been executed on Linux. The QNX 8 cancellation canary is source only. No QNX build, QNX target execution, physical motor test or production bug discovery is claimed.

## Run it

Requirements: Linux, Python 3.10 or newer, CMake 3.16 or newer, and a C11 compiler. The workbench uses only the Python standard library. No account, API key, network service, Python package download or GPU is required for the Linux path.

```sh
./scripts/verify-local.sh
```

This creates a fresh local output directory and runs the C checks, Python tests and exported regression suite. There is no remote CI workflow in this repository.

To generate a larger experiment:

```sh
python3 -S -m deadline_lab campaign --out artifacts/campaign --per-split 40
```

Open `artifacts/campaign/report.html` in a browser. The offline viewer contains recorded results, a filterable campaign table and reduced witnesses. An interrupted campaign can continue with `--resume`; completed run artifacts are checked against their hashes, scenario and binary before reuse.

To demonstrate a bug and its rejection:

```sh
# Exit 1 is expected: the deliberately flawed fixture authorises an expired command.
python3 -S -m deadline_lab run examples/expiry.json \
  --mode omit_expiry --out artifacts/expiry-broken

# Exit 0 is expected: the reference rejects it and still accepts the healthy probe.
python3 -S -m deadline_lab run examples/expiry.json \
  --mode reference --out artifacts/expiry-reference

# Turn the reduced failures into a normal regression gate, with JUnit output.
python3 -S -m deadline_lab regress regressions/suite.json \
  --out artifacts/regressions --verify-mutants
```

`run` exits 0 for PASS, 1 for FAIL and 2 for INCONCLUSIVE or an input/infrastructure error. `regress` exits 0 only when its expectations hold. A deliberately broken fixture is expected to fail; the sensitivity check treats that as success for the test harness. The candidate implementation itself must pass.

## What is implemented

The portable C core tracks immutable commands, authority generations, expiry, acknowledged cancellation and per-session deduplication. It has bounded storage and rejects new commands when that storage is full instead of forgetting old effects or cancellations.

The Linux runner starts only its own C workers and a separate virtual-plant process. It uses actual SIGSTOP/SIGCONT and SIGKILL/restart operations. Explicit test hooks model delayed delivery and an effect whose acknowledgement is lost. It never accepts an external PID or shell command from a generated scenario.

The plant observes effect messages on a separate pipe and owns the simulated integer state. It does not import the controller or its mutation logic. A separate Python checker compares those effects against issued commands and recorded lifecycle actions. It does not accept a success reply as proof that the effect was correct.

The generator combines an authored, bounded action grammar using fixed seeds. It is not coverage-guided fuzzing. The reducer re-executes real processes and preserves a selected violated property. Every accepted reduction runs twice, and each final witness is replayed five times against the flawed and reference implementations in the recorded campaign.

The exporter writes standalone JSON scenarios, a regression-suite descriptor and JUnit results. The reference must accept an independent healthy command after each scenario. A reject-everything implementation fails that check.

## Recorded checkpoint

See `docs/progress-2026-11-09.md` for the complete result and limits. The delivered evidence package contains:

| Check | Observed result |
| --- | --- |
| Main campaign | 80 generated histories across 6 implementations, 480 scenario executions |
| Reference implementation | 80 PASS, 0 FAIL, 0 INCONCLUSIVE; 301 observed effects |
| Seeded fault families | All four families detected in discovery and held-out seed sets |
| Reduced witnesses | Four witnesses with 4, 4, 4 and 5 actions |
| Final witness replays | Each flawed/reference pair reproduced the expected result 5 times each |
| Python workbench tests | 28 passed |
| Portable C checks | 1,052 assertions passed |
| Sanitizer checks | C test executable plus 6 scenario executions, no diagnostics observed |
| Exported regression suite | 8 expected outcomes observed, including mutant sensitivity checks |
| QNX native gate | NOT RUN; qcc and QEMU were absent from PATH in this environment |

These counts describe bounded synthetic experiments. They are not a safety certification, a motor-performance benchmark or a numerical probability of winning a competition.

## QNX-specific work

`qnx/server.c` and `qnx/client.c` form a native cancellation canary using actual QNX APIs, including `MsgReceive`, `MsgSend`, `TimerTimeout`, `_NTO_CHF_UNBLOCK`, `MsgInfo` and `MsgError`. They are guarded against compilation as a pretend Linux implementation. There are no vendored QNX headers, binaries, images or license files.

```sh
# Run only after sourcing a properly licensed QNX SDK environment.
./scripts/build-qnx.sh

# On a QNX target with Python 3 and the built executables:
python3 scripts/qnx-canary.py --bin ./build-qnx --out native-results
```

The build helper exits 77 when qcc is unavailable. The canary runner exits 77 and reports NOT_RUN outside QNX. Neither condition is reported as a passed native test. Exact setup, permission requirements and acceptance evidence are in `docs/qnx-native-gate.md`.

## Project map

| Location | Purpose |
| --- | --- |
| `include/`, `src/` | Portable C contract and real-process fixture |
| `deadline_lab/` | Scenario grammar, runner, plant, checker, reducer, export and report |
| `qnx/` | Unvalidated native QNX cancellation canary and toolchain file |
| `tests/` | Core and workbench regression tests |
| `examples/`, `regressions/` | Readable manual examples and automatically reduced tests |
| `docs/` | Architecture, evidence boundaries, source references and submission gates |
| `evidence/` | Recorded campaign and validation outputs in the delivered package |

## What remains

Compile and run the native canary on QNX 8. Integrate its transport and effect observations into the generic reducer. Exercise an independently authored QNX application. Verify a fresh developer can reproduce a useful failure without us operating the environment. Those are the next competitive evidence gates, not another round of interface decoration.
