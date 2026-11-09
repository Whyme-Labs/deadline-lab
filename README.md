# Deadline Lab

Find a recovery or ordering failure, observe the effect, reduce the failing sequence, and export a regression test.

**v0.2.0 is an engineering prototype, not a competition-ready release.** The C fixture and an independently authored, unmodified nginx HTTP/file server have run on Linux. The native QNX source now has a separate effect observer and a shared reduction entry point, but has not compiled or executed on QNX. No physical actuator, production vulnerability or safety certification is claimed.

## Run the local checks

Requirements: Linux, Python 3.10 or newer, CMake 3.16 or newer, and a C11 compiler. No Python package installation, account, GPU or API key is needed.

```sh
./scripts/verify-local.sh
```

The independent-target checks additionally require a locally installed nginx with its DAV module. They use a new foreground process, loopback-only sockets and files beneath the selected output directory. They do not reload or change an existing nginx service.

```sh
./scripts/verify-external.sh
```

The latter returns 77 when the optional target is absent, not a passing result. `verify-local.sh` skips optional nginx execution tests when nginx is absent. A successful core-only check does not close the independent-target gate.

## See the newly validated failure

An expiry guard is not an ordering guard. Both requests can still be valid when a delayed older request overwrites a newer value.

```sh
# Expected exit 1. The older valid request overwrites the newer file value.
python3 -S -m deadline_lab external-run examples/external/reordering.json \
  --policy deadline --out artifacts/reordering-broken

# Expected exit 0. The gateway also checks command sequence order.
python3 -S -m deadline_lab external-run examples/external/reordering.json \
  --policy fenced --out artifacts/reordering-fixed

# Execute the reduced cases as normal regression checks, including negative controls.
python3 -S -m deadline_lab external-regress regressions/external/suite.json \
  --out artifacts/external-regressions --sensitivity
```

Output directories must not already exist. Each run includes a healthy write so rejecting everything cannot pass. The checker reads the bytes nginx wrote rather than accepting an HTTP success response as proof of the effect.

This is not an nginx flaw. The gateway policies, test requirements and cooperative delay hooks are ours. nginx supplies independently authored HTTP processing and file effects. This validates reuse of the workbench beyond the original C fixture, not discovery of an unknown external bug or native QNX portability of nginx.

For the complete external campaign, reduction and offline report:

```sh
python3 -S -m deadline_lab external-campaign \
  --repetitions 5 --out artifacts/external-campaign
```

Open the generated `report.html`. Missing, altered, reordered or incomplete evidence produces INCONCLUSIVE. Hashes detect accidental corruption, not adversarial forgery. Recheck a saved run with:

```sh
python3 -S -m deadline_lab external-recheck artifacts/reordering-fixed
```

## What ran in the recorded v0.2.0 checkpoint

| Check | Observed result |
| --- | --- |
| Python unit/integration suite | 59 passed in this environment, including optional nginx execution |
| Portable C tests | 1,052 core assertions and 9 effect-pipe assertions passed |
| Independent-target campaign | 10 parameterised histories across 4 policies, 40 runs |
| Timeout-only policy | 10 failed application contracts |
| Expiry-only policy | 5 passed expiry cases, 5 failed still-valid reordering cases |
| Expiry plus sequence fence | 10 passed, no inconclusive run |
| Reject-everything control | 10 failed healthy-progress checks |
| Reduced external witnesses | 7 to 3 actions and 6 to 3 actions |
| Witness replay | Each bad/good pair reproduced its expected outcome 5 times |
| External regression suite | All 4 expectations met; intentionally regressed candidate correctly failed |
| Offline evidence recheck | All 68 retained final external run bundles reproduced their verdict/properties |
| Sanitizers | Both C test executables and 6 process scenarios, no diagnostics observed |
| Native QNX gate | NOT RUN; both compiler and target entry points returned 77 |

The 40 runs are not 40 distinct applications or a statistical estimate of general detection accuracy. The 68 rechecks include final campaign, response-loss controls, witness replays and regression runs. They do not add 68 new executions. Intermediate reducer trials are executed but not all retained as artifact bundles.

The inherited v0.1.0 campaign remains in `evidence/campaign-v1`. Its 480 runs are historical results, not freshly rerun native experiments. The original eight regression expectations still pass after this revision.

## Original process-fault workflow

```sh
python3 -S -m deadline_lab run examples/expiry.json \
  --mode omit_expiry --out artifacts/expiry-broken
python3 -S -m deadline_lab run examples/expiry.json \
  --mode reference --out artifacts/expiry-reference
python3 -S -m deadline_lab regress regressions/suite.json \
  --out artifacts/core-regressions --verify-mutants
```

This path operates compiled C workers and a separate integer-state observer. Actual suspension, resumption and termination supplement explicit delivery and response-loss hooks. It checks generation fencing, expiry, acknowledged cancellation, bounded deduplication and healthy progress. It does not model motor electrical or mechanical dynamics.

The shared reducer accepts an adapter runner and a validator. It repeats candidate failures and audits one-action deletions. Its claim is grammar-constrained deletion-1-minimality, not a globally shortest sequence, coverage-guided fuzzing or exact scheduling replay.

## Native QNX gate

An appropriately licensed SDK and a real QNX target remain required. No proprietary SDK headers, binaries, target images or licence material are included.

```sh
# On a supported development host after sourcing the licensed SDK environment:
./scripts/build-qnx.sh

# On the QNX target with Python 3, this source package and compiled binaries:
python3 -S scripts/qnx-canary.py --bin ./build-qnx --out native-results --repetitions 5

# Only after a native failure actually reproduces:
python3 -S scripts/qnx-reduce.py examples/native/unblock.json \
  --bin ./build-qnx --out native-reduction
```

The server now delivers virtual effects through a dedicated pipe to a separate observer. The checker cross-checks those effects against client results, actual unblock activation and server lifecycle events. A missing observer, missing activation or unclean shutdown cannot be counted as a successful cancellation test. Fourteen offline checker/guard tests use records explicitly labelled synthetic; they do not emulate QNX APIs or establish native compatibility.

See `docs/qnx-native-gate.md` for the precise platform semantics and remaining review work.

## Evidence limits and next decision

An expired dispatch, an expired physical action and an unknown outcome after a lost response are different problems. This version does not conflate them. The HTTP fence only governs admission at one serial gateway. It cannot retract an already dispatched operation, establish a hard backend commit deadline, or provide durable exactly-once physical actions.

The next competition-critical gate is actual QNX compilation and repeated native observations, followed by a fresh developer's reproduction trial. A tested independent Linux backend is progress, but it does not substitute for either gate.

See `docs/progress-v0.2.0.md`, `docs/external-target.md`, `docs/submission-gates.md` and `docs/references.md`. All work remains local. No remote repository, CI, installation, purchase or deployment is performed by the verification scripts.
