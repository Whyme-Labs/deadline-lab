# Deadline Lab v0.5.0 checkpoint

10 November 2026, UTC+8. Continued from the verified v0.4.0 archive. Its SHA-256 was `a4a47a9e71230c3c25c73e9fa590a50f4e9d173e750564716c696ebf5196b383`; all 90 inherited source files matched the source manifest before editing.

## Completed milestone

A native experiment can now be prepared as a small target folder, executed without SSH or target Python, and returned as files for checking on the development host. The prepare, relocate, run and import workflow has been executed with the real portable Linux collector and explicitly non-native process fixtures.

The QNX-specific code is still uncompiled and unexecuted. This is an offline handoff milestone, not native acceptance, a new application bug discovery or a competition-ready submission.

## What changed

The host keeps an original request with a fresh token, scenario, policy, exact binary identities and source/build record identities. Preparation requires an existing completed native build of the current executable-source revision. It refuses missing artifacts, changed binaries, source mismatches, binary symlinks and existing output directories.

The target receives only four project executables, two provenance files and a POSIX shell wrapper. Its result contains three files. No target Python, source checkout or SSH daemon is required by this route. The wrapper still requires `/bin/sh`, `mkdir` and the ordinary runtime libraries used by the compiled binaries. It does not install software or change a security policy.

The importer compares returned evidence against the host's original request, not a request supplied by the target. It reuses the existing native materialisation and checker. Transport completion does not establish application correctness. A portable test result is always `TRANSPORT_ONLY`; it cannot pass the native gate.

Offline records do not claim that the host personally observed or reaped a remote process. The target collector's own direct-child cleanup records are still checked. Hashes detect mismatched or corrupted artifacts, not a malicious author fabricating a complete consistent evidence set. The request nonce is not a durable single-use ledger or a trusted clock.

## Concrete execution result

A modified executable still ran and produced a complete portable capture. The importer rejected it because its bytes differed from the executable pinned during preparation. This exercises wrong-deployment detection with an actual running program, not a mocked hash comparison.

A relocated handoff also ran successfully. In the retained trial the target PATH contained only `mkdir`. The shell came from the absolute `/bin/sh` entry point; the collector launched its project binaries by absolute path. This checks the executed portable dependency path, not a QNX target image.

## Retained handoff trial

| Case | Observation |
| --- | --- |
| Normal execution and import | TRANSPORT_ONLY, as expected |
| Relocated target folder | TRANSPORT_ONLY, as expected |
| Executable changed after preparation | INCONCLUSIVE, mismatch detected |
| Child stalls during readiness | INCONCLUSIVE, collector exited 78 |
| Capture associated with a different host request | INCONCLUSIVE |
| Truncated return stream | INCONCLUSIVE |
| Missing target completion file | INCONCLUSIVE; available raw bytes retained |
| Diagnostic stderr added to returned capture | INCONCLUSIVE |

All eight expected outcomes occurred. The trial contains four real collector executions and four additional import checks against modified or reassociated returned files. These are not eight native executions. All eight imported artifact manifests verified. Temporary binary handoffs were removed. The raw records are under `evidence/v0.5.0/offline-rehearsal`.

## Validation

The full Python suite passed 156 tests, including 26 new offline handoff tests and the available nginx execution tests. The portable C programs passed 1,052 core assertions, nine effect-pipe assertions and four SHA-256 known-answer vectors. The eight core regression expectations and four external regression expectations remained satisfied.

The local, external, collector and offline verification scripts all passed. The collector script retains its separate portable smoke checks; these are not added to the new offline trial count. No new sanitizer or native timing claim is made in this version. Earlier sanitizer and campaign records remain labelled by their historical versions.

A fresh source-only ZIP was extracted into a different path containing spaces. Its complete source manifest was verified, then all four verification scripts rebuilt and passed without reusing the working build directory or downloading dependencies. This is an automated package trial, not an independent developer's usability study.

## Unresolved native dependency

The SDK prerequisite check returned `NOT_RUN`, exit 77. The native offline preparation command also returned 77 without creating a purportedly ready target folder. No `qcc`, `QCC`, checked QEMU executable, SDK environment or SSH executable was available here. A public OpenSSH package download attempt failed and installed nothing. The new offline route removes SSH as a requirement for collecting the first native case; it does not supply the QNX SDK or runtime image.

The official QNX setup path requires a myQNX account and an appropriate activated licence, then the SDK and a compatible target. The [licence codelab](https://qnx.github.io/codelabs/get-non-commercial-qnx-license/index.html) and [QEMU target guide](https://www.qnx.com/developers/docs/qnxeverywhere/com.qnx.doc.target_images/topic/qsti_qemu/about.html) were reviewed on 10 November 2026, UTC+8. No licence terms were accepted here and no licence material is included.

## Next action

Use an authorised QNX SDP 8 build and a booted QNX target to execute the first reference and negative-control tickets in `docs/offline-native-run.md`. No login credentials or licence keys need to be sent with returned captures. One native case does not close acceptance. Repeated comparisons, reduction, regression export and sensitivity checks remain required; the existing live workflow automates those steps, while this offline route handles individual cases.

Further host-only test volume would not resolve this platform gap. Actual native evidence and an independent developer reproduction remain the next competition-relevant milestones. No prize probability, production bug, physical actuator behaviour, safety certification or universal cancellation claim follows from this release.

Everything remains local. There was no GitHub push, remote CI, purchase, deployment to a user machine, hardware operation or alteration of another project. The release excludes compiled binaries, SDK components, licence material and credentials.
