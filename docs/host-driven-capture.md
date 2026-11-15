> v0.5 adds an [offline handoff](offline-native-run.md) for targets without SSH. The original live route below remains available.

# Host-driven capture with a minimal target

## Scope and status

Version 0.4 introduces a C collector so the QNX target no longer needs Python or the Python source tree for the new capture path. Python, the reducer and JUnit generation stay on the POSIX development host. The old on-target Python path remains available for compatibility.

The v0.6.0 collector has compiled with QNX SDP 8 and completed native acceptance over SSH on a QNX 8 AArch64 QEMU target. Five reference/negative pairs, reduction, five regression replay pairs and the deliberately regressed candidate produced their expected results. See the [QNX codelab](qnx-codelab.md) and release evidence. The separately named Linux process-I/O fixtures remain portable transport tests; they do not implement QNX APIs.

## Target footprint

After a successful build with an authorised QNX SDP 8 environment, copy these six files from the build directory to a private directory on an approved, booted QNX target:

- `dl-capture`, `dl-qnx-server`, `dl-qnx-client`, `dl-qnx-abi`.
- `build-record.json` and `source-manifest.json`.

Use the target's normal QNX runtime and C library. Do not copy SDK components, runtime images, licence material or unrelated files into a public project. No Python interpreter, pip, CMake, compiler, SHA-256 command or application source tree is required on the target by this path. The host needs Python 3.10 or newer. Using the SSH path also requires an existing working SSH client/server connection and a known, verified host key. Nothing here installs or enables SSH, changes security abilities or accepts licence terms.

## Exact workflow

Build on the developer host, after sourcing the authorised SDK environment:

```sh
./scripts/build-qnx.sh --out artifacts/qnx-build
```

Transfer the six files using the approved deployment method. Keep the identical host source revision that produced them. The example below uses an existing SSH alias named `qnx-lab` and a target directory `/tmp/deadline-bin`. Replace these with the actual approved target.

```sh
python3 -S -m deadline_lab.native_workflow accept \
  --collector --ssh qnx-lab --bin /tmp/deadline-bin \
  --out artifacts/native-host-acceptance
```

The command conducts the paired native campaign, rechecks observations, reduces the failure, exports a regression and checks that a deliberately regressed candidate fails. It uses the same strict acceptance gate as the legacy path. It will not pass on Linux with a relabelled fixture. It requires actual native records, build/binary matches, observed pre-commit unblock activation and healthy operation.

For a single native scenario:

```sh
python3 -S -m deadline_lab.capture examples/native/unblock.json \
  --ssh qnx-lab --bin /tmp/deadline-bin --mode reference \
  --out artifacts/native-single
```

The SSH transport uses batch mode, no pseudo-terminal and strict host-key checking. It does not accept new host keys, send passwords or construct an unquoted remote command. The alias may use the developer's existing SSH configuration. The SSH route was exercised on the recorded QNX target. Local collector execution on a QNX system is available by omitting `--ssh`; in that case Python runs locally on the same machine as the collector.

## What the collector does

The collector hashes its designated binaries before and after the run. It runs the ABI probe, starts the server with a private effect pipe, parses a bounded readiness message and launches the requested clients. It appends a healthy call. It reads stdout, stderr and the effect pipe concurrently with `poll`, records target monotonic timestamps and waits for child completion. It never infers a virtual effect from a successful client reply.

All test binaries are explicit absolute paths. Child creation uses `posix_spawn`, not a shell or a target Python module. `--transport-fixture` is a local-test mode with different binaries and an explicit non-native origin. It cannot produce QNX acceptance.

Input is bounded to eight requested calls plus the healthy call. Each stdout/stderr channel is bounded to 64 KiB. Effect lines are bounded to 256 bytes, and an observation may contain at most 128 effects. The target run budget is at most 60 seconds, excluding bounded cleanup and export. These are watchdog budgets under ordinary OS scheduling, not hard-real-time guarantees.

The collector creates a private scratch directory for streaming mode and removes only files it recorded there. It owns and signals only its direct child processes. It does not kill by name, reload an existing service, write motor registers, acquire elevated privileges or operate other applications. This is not a sandbox for hostile binaries. The demonstration child programs do not create descendants. An escaped child process, a kernel hang, uninterruptible I/O or SIGKILL of the collector is not a proven cleanup case.

## Evidence format and import

The stream begins with `DLCAP1`, contains bounded named-file frames and ends with `END`. The host parses the complete bounded stream before writing allow-listed files. Duplicate frames, traversal paths, oversized lengths, trailing bytes and truncation are rejected.

A fresh token binds the requested scenario and policy to the received capture. Raw client output, server logs, effect messages with observer timestamps, ABI output, binary identities and source provenance remain in the result directory. The host derives the existing native evidence format from those raw records. Offline checking compares the derived evidence with the raw capture again. The host never substitutes its own clock for the target's observation timestamps.

Hashes and tokens detect accidental corruption, wrong deployment and stale capture reuse. They do not authenticate a dishonest author who fabricates an entire consistent record. The collector hash is a file identity, not hardware-backed remote attestation. Linux cannot compile the QNX-only client, server or ABI source with fake headers through this workflow.

## Failure semantics

A completed collection is not a passed application test. The native checker still decides PASS, FAIL or INCONCLUSIVE from the application contract. Collector failures and partial transport cannot support a passing native result. Missing native prerequisites return NOT_RUN and exit 77.

The target collector has a deadline independent of the host launcher. A network disconnect or the host killing its own SSH process cannot prove that a remote process was reaped. Such a run stays inconclusive. The host does not issue a broad remote kill command to hide that uncertainty.

`TimerTimeout` and the unblock flag still refer to the same cooperative virtual-effect test. The collector does not improve cancellation semantics, make timeout equivalent to rollback, prove physical safety or measure worst-case actuator latency.

## Reproduce the executed portable milestone

```sh
./scripts/verify-capture.sh
```

The process-I/O tests include partial greetings, child stalls, output floods, truncated or oversized effects, wrong process identities, early exits, SIGTERM handling and forced termination of a stubborn owned child. Successful runs are also executed with a target PATH that contains no interpreter or helper utilities. This proves the dependency claim only for the executed portable collector and fixture programs.

The retained campaign labels every observation `posix-capture-test` or `unsupported-host`. It includes deliberate refusal of the native path on Linux. An automated fresh-package test is not an outside developer's usability trial.

## References

Implementation uses the official QNX 8 documentation for [posix_spawn](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/p/posix_spawn.html), [poll](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/p/poll.html), [TimerTimeout](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/t/timertimeout.html) and the [SSH utility](https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/s/ssh.html). Reviewed 10 November 2026, UTC+8. Documentation compatibility is not successful native compilation.
