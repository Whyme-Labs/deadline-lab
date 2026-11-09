# Deadline Lab v0.4.0 checkpoint

10 November 2026, UTC+8. Local continuation of the delivered v0.3.0 archive at source baseline `d2b0c51`. The input archive SHA-256 was `1ec23af8a720361057610a5f8eaf287e72862c986b71f1a031a849f2ab898d26`; its 79 source files matched the included source manifest before editing.

## Completed milestone

The new host-driven capture path removes the requirement for Python and a source checkout on the QNX target. A portable C collector now launches owned test processes, drains their outputs and a separate effect pipe, applies size and time budgets, records binary identities, and exports a framed evidence bundle. The development host imports that evidence and connects it to the existing native checker, reducer and regression workflow.

The collector and transport were compiled and executed on Linux. The QNX-specific programs have still not compiled or executed. The live SSH path has not run. This completes a local deployment and capture milestone, not the native acceptance milestone or the competition submission.

## Why this is useful

The previous acceptance workflow required a Python installation and the project source tree on the target. That is unnecessary for collecting a small native experiment. The new deployment contract is four project binaries plus two provenance files. Python, reduction, evidence checking and JUnit stay on the developer host. No target Python, pip, compiler, SHA-256 utility or source tree is required by the new collector path.

The executed dependency check set the target subprocess PATH to a directory containing no interpreter or helper utilities and used absolute executable paths. This establishes the dependency result for the executed Linux collector and test fixtures, not for an untested QNX binary.

## What changed

- A C collector uses `posix_spawn`, `poll`, monotonic deadlines and bounded framing. It observes the effect pipe separately from server success replies.
- Host import retains the raw capture and target timestamps. Offline checking compares derived records back to the capture before accepting a native verdict.
- SHA-256 identities bind the declared build files and binary files before and after collection. A fresh request token rejects accidental reuse of an unrelated capture. These checks are not remote attestation or protection against an author fabricating all evidence.
- The existing native acceptance and exported regression commands accept `--collector` and an optional existing SSH alias. SSH command construction uses strict host-key checking and quoted arguments. No SSH session was available here.
- A separate set of POSIX process-I/O fixtures exercises the collector. Their executable names, ABI record and evidence origin differ from native QNX. They do not implement or emulate QNX APIs and cannot pass the native acceptance gate.

The target collector caps requested calls at eight plus one healthy call, each output channel at 64 KiB, effect lines at 256 bytes and observed effects at 128. A completed capture is not an application PASS. Incomplete capture cannot support passing native evidence.

## Recorded validation

| Check | Observed result |
| --- | --- |
| Complete Python suite | 130 passed, including locally available nginx execution tests |
| C contract tests | 1,052 assertions passed |
| C effect-pipe tests | 9 assertions passed |
| C SHA-256 tests | 4 known-answer vectors passed, including one million `a` bytes |
| Retained collector campaign | 48 expected outcomes met across 16 cases and 3 repetitions |
| Campaign composition | 45 real POSIX process-I/O runs plus 3 deliberate native refusals on Linux |
| Retained capture recheck | All 48 manifests, framed raw bytes, unpacked files, outcomes and relevant binary digests matched |
| Sanitized C tests | All 3 C test executables passed with AddressSanitizer and UndefinedBehaviorSanitizer |
| Sanitized capture suite | All 39 capture tests passed in four completed batches, with no observed sanitizer diagnostics |
| Portable C static analysis | No diagnostics for the five analysed portable C implementation files |
| Existing core regressions | All 8 expectations met |
| Existing external regressions | All 4 expectations met against the installed nginx backend |
| SDK prerequisite check | NOT_RUN, exit 77; `qcc`, `QNX_HOST` and `QNX_TARGET` unavailable |
| Host-driven native acceptance | NOT_RUN, exit 77, on the actual Linux environment |

The 48 retained cases cover normal collection, a 100-effect burst, a large but permitted stderr stream, a partial greeting, wrong process identity, early exit, output overflow, partial or malformed effects, effect-size and count limits, termination escalation, a stalled client, client output overflow, nonzero client exit, and Linux native refusal. Actual direct-child cleanup and private scratch removal were checked. The host decoder separately tests truncation at every byte of a sample frame and rejects duplicate frames, unsafe names, oversized streams, malformed JSON and trailing data.

These counts measure transport correctness under the declared tests. They are not new application bug discoveries, a general detection rate, a hard latency bound or a probability of winning. Offline rechecks are not additional process runs. Prior v0.1 through v0.3 evidence remains explicitly historical.

## Execution issues and boundaries

Several whole-suite sanitizer invocations exceeded the tool-call wall-time limit. Their partial logs remain in the evidence directory and are not successful tests. Instrumented binaries were also much larger, and hashing them consumed the original short test budgets before some child processes started. Those early runs did not establish the intended child-fault case. The final sanitizer suite used an explicit test-only budget multiplier of eight and four completed batches, totalling 39 tests. Production collector limits were unchanged. The normal-build campaign used its original 400 ms budget.

An initial static-analysis invocation used the wrong worker filename. That failed command is retained separately. The final invocation analysed the actual `worker_posix.c` together with the other four portable implementation files. QNX-only source was not compiled or analysed through substituted Linux headers.

Cleanup is limited to owned direct child processes and recorded scratch files. The tool is not a sandbox for hostile applications. Descendants, a kernel hang, uninterruptible I/O, killing the collector with SIGKILL and remote cleanup after a network disconnect are not established cleanup cases. Host timeouts and target watchdog budgets are not hard-real-time guarantees.

The framed stream is bounded, but its integrity metadata is not authentication. Native effect observations remain virtual and cooperative. No physical motor, current optimisation, torque measurement, thermal compensation or universal cancellation guarantee was tested.

## Fresh-package trial

A source-only archive containing 90 source files was extracted into a new directory whose path contains spaces. Its full source manifest and executable script modes were verified. The local, external and collector verification commands then built from scratch and passed without downloading packages, installing dependencies or using the original build directory. The existing host compiler and nginx installation were reused. The collector command performed a separate 16-case one-repetition campaign. That additional smoke check is not included in the 48-case retained primary campaign count.

This is an automated fresh-package trial, not an outside developer's usability assessment. The first shell invocation accidentally used the parent directory and returned a missing-script error. That log was preserved; the documented commands were then run from the extracted project directory and passed. No source change was needed for that invocation error.

## Reproduction

From the extracted source directory:

```sh
./scripts/verify-local.sh
./scripts/verify-external.sh
./scripts/verify-capture.sh
```

The external command requires an already installed nginx with DAV support and starts only its own loopback instance. The capture command builds and runs the non-native collector tests and a one-repetition campaign. It does not compile QNX or open SSH.

For a real native build, source an authorised QNX SDP 8 environment and use:

```sh
./scripts/build-qnx.sh --out artifacts/qnx-build
```

After approved deployment of the six project files and verification of the existing SSH connection:

```sh
python3 -S -m deadline_lab.native_workflow accept \
  --collector --ssh qnx-lab --bin /tmp/deadline-bin \
  --out artifacts/native-host-acceptance
```

The native success path may still require corrections after real compilation and execution. `docs/host-driven-capture.md` records the exact deployment contract and failure semantics. No SDK, runtime image, licence material or compiled binary is included in the release.

## Next decision gate

The required next evidence is unchanged: compile with the genuine SDK, execute on an authorised QNX target, observe the actual unblock-before-effect behaviour, reduce a native failure and verify the corrected implementation. The new collector removes the target-Python dependency but does not supply the missing platform. An outside developer trial remains a separate uncompleted milestone.

This revision improves deployability and evidence collection. It does not justify calling the project prize-ready. No GitHub push, remote CI, purchase, licence acceptance, remote deployment or changes to another project occurred.
