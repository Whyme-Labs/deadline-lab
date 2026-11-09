> v0.5: a source-free target folder can now be run and imported without SSH. See [offline native run](offline-native-run.md). Actual native compilation/execution is still required.

> v0.4 update: the host-driven C collector path removes Python from the target requirements. See [host-driven capture](host-driven-capture.md). The original on-target Python workflow below remains available. Native execution is still unverified in this environment.

# Native QNX handoff

Status for v0.3.0: the source-level workflow is connected, but no native compilation or execution has occurred in this environment. The local shell helpers returned 77. Do not treat a Linux regression suite or synthetic native-record fixture as a completed native gate.

## Needed inputs

Use a development host with an appropriately licensed QNX SDP 8 toolchain, CMake and Python 3.10 or newer. Source its SDK environment so qcc, QNX_HOST and QNX_TARGET are available. Use a booted compatible QNX target with Python 3.10 or newer and permission to create the required public channel. A physical board is optional; the target may be an authorised QNX virtual machine. This package does not install an SDK, accept licence terms, create a cloud instance or alter security policy.

The current container has no qcc or QCC on PATH and no checked QEMU executable. No accessible remote SDK/target was confirmed. Installing QEMU alone would not supply QNX or a development licence.

## Build on the development host

From any directory:

```sh
/path/to/deadline-lab/scripts/build-qnx.sh --out /path/to/qnx-build
```

Output must be a new directory. The default supported variant is gcc_ntox86_64. For the supported AArch64 variant:

```sh
/path/to/deadline-lab/scripts/build-qnx.sh \
  --variant gcc_ntoaarch64le --out /path/to/qnx-arm-build
```

The helper captures qcc variant output, configuration and compilation logs, the executable-source manifest and output ELF identities. It records COMPILED only after those steps succeed. ELF checks establish expected bitness and machine family, not native runtime behaviour. No QNX header substitute or Linux binary can satisfy the source's actual-SDK guard.

Successful output binaries and provenance are under the selected output directory's `build` subdirectory. The native ABI executable is source-only in this release; its QNX execution is still required.

## Run on the target

Transfer the identical source tree and your own build directory through your approved method. Do not redistribute SDK headers, QNX runtime files or licence material in the public hackathon repository. Build logs may contain host paths and should be reviewed before publication.

On QNX:

```sh
./scripts/verify-native.sh --bin /path/to/qnx-build/build \
  --out artifacts/native-acceptance
```

The intended pipeline is:

1. Check real target identity, native binaries, source identity and ABI observation.
2. Execute five reference/omitted-cancellation pairs using a scenario with normal calls surrounding timeout calls.
3. Re-evaluate each case from independent observer records and target lifecycle logs. No summary-only pass is accepted.
4. Require genuine pre-commit unblock activation and healthy progress for the reference. Require the negative control to violate the declared policy.
5. Reduce the failure with repeated tests and a complete one-action-deletion audit.
6. Export a native regression suite, replay the bad/good comparison five times and reject an intentionally regressed candidate.

This sequence is implemented, not yet observed end-to-end on QNX. The output `acceptance.json` is successful only when its status is ACCEPTANCE_COMPLETE. INCONCLUSIVE and NOT_RUN never count as acceptance.

## Reuse the native regression

After a genuine successful native run:

```sh
python3 -S -m deadline_lab.native_workflow regress \
  artifacts/native-acceptance/regressions/suite.json \
  --bin /path/to/qnx-build/build --out artifacts/native-regression \
  --sensitivity
```

This writes ordinary JUnit XML. A failing candidate is a test failure; missing execution is a test error. Both return nonzero. An unrelated environment cannot earn a pass by skipping the native tests.

To re-evaluate the paired evidence without re-running the target:

```sh
python3 -S -m deadline_lab.native_gate \
  artifacts/native-acceptance/canary --out native-gate-recheck.json
```

## Limits

A successful native canary would establish this bounded virtual-effect cancellation contract on that build and target. It would not prove physical actuator safety, worst-case timing, durable exactly-once effects, usefulness to an independent developer or competition novelty. An external reproduction trial remains a separate milestone.

The evidence format detects accidental corruption and several semantic inconsistencies. It is not a remote-attestation system and cannot authenticate a malicious author who fabricates a complete mutually consistent evidence set.
