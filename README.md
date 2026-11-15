# Deadline Lab

Turn recovery and ordering failures into small, replayable regression tests.

A client timeout does not prove that a server did nothing. Deadline Lab runs a
failure scenario, observes the resulting virtual effects, reduces a reproducible
failure, and exports a regression with JUnit output. A healthy-operation probe
prevents a server that rejects every request from passing.

## QNX demonstration

Version 0.6.0 has compiled with the genuine QNX SDP 8 toolchain and run on QNX 8.0
AArch64 in QEMU. Python analysis stays on the development host. Four project C
executables and two provenance files run on the target, with no target Python.

The demonstration uses QNX message passing, `TimerTimeout`, unblock pulses and
`MsgInfo`. Our reference server cancels a pending virtual operation when it
observes the relevant unblock request. Our deliberately flawed `ignore_unblock`
server applies the operation anyway. A separate pipe observer records the effect.
This is a seeded application-policy defect, not a QNX vulnerability.

Recorded on 16 November 2026:

| Check | Observed result |
| --- | --- |
| Native build | QNX SDP 8, qcc 12.2.0, `gcc_ntoaarch64le` |
| Native target | QNX 8.0.0, `QEMU_virt`, AArch64, two CPUs, 512 MiB |
| Native C tests | 1,052 core, 9 effect and 4 SHA-256 assertions passed |
| Native acceptance | Five reference/negative pairs met all ten expectations |
| Reduction | Five scripted calls reduced to one timed call; healthy probe remains separate |
| Exported regression | Five paired replays passed; deliberately regressed candidate rejected |
| Evidence check | Captures rechecked from raw observations and matching build identities |

Get the [source and evidence release](https://github.com/Whyme-Labs/deadline-lab/releases/tag/v0.6.0)
and follow the [QNX codelab](docs/qnx-codelab.md). Earlier results under `evidence/`
and the versioned progress documents are historical checkpoints.

## Try the Linux workflows

On macOS or Linux with a running Docker-compatible engine:

```sh
./scripts/verify-container.sh
```

This builds an Ubuntu validation image and runs the core, nginx, collector and
offline-transfer checks. Test execution uses container loopback with external
networking disabled. The SDK, licence and home directory are not build inputs.

On Linux with Python 3.10+, CMake 3.16+ and a C11 compiler:

```sh
./scripts/verify-local.sh
./scripts/verify-external.sh  # also needs nginx with its DAV module
./scripts/verify-capture.sh
./scripts/verify-offline.sh
```

No Python package installation, account, GPU or API key is needed for these Linux
checks. The optional external check exits 77 if nginx is missing. Linux results
do not establish native QNX behavior.

## Reproduce the QNX workflow

Use your own appropriately licensed QNX SDP 8 SDK and a booted QNX target. This
repository distributes no SDK, runtime image or licence material. With the SDK
environment sourced, build for the demonstrated AArch64 target:

```sh
./scripts/build-qnx.sh --variant gcc_ntoaarch64le --out artifacts/qnx-build
```

Deploy `dl-capture`, `dl-qnx-server`, `dl-qnx-client`, `dl-qnx-abi`,
`build-record.json` and `source-manifest.json` from `artifacts/qnx-build/build`
to `/tmp/deadline-bin` on your target. With an existing SSH alias and a verified
host key:

```sh
python3 -S -m deadline_lab.native_workflow accept \
  --collector --ssh qnx-lab --bin /tmp/deadline-bin \
  --out artifacts/native-acceptance
```

A complete run produces `acceptance.json`, raw captures, a reduction record,
exported regressions and JUnit reports. Output directories must be new. Missing
or inconsistent evidence stays INCONCLUSIVE; absent prerequisites return NOT_RUN.

Replay the committed reduced case:

```sh
python3 -S -m deadline_lab.native_workflow regress regressions/native/suite.json \
  --collector --ssh qnx-lab --bin /tmp/deadline-bin \
  --out artifacts/native-regression --sensitivity
```

The [offline handoff](docs/offline-native-run.md) supports targets without SSH.
Prepare a target folder on the host, run it on QNX and import the returned capture
against the original host request. Offline transfer alone does not close the
repeated acceptance gate.

## Independent Linux target

The nginx adapter checks actual HTTP/file effects from an unmodified nginx
process. Our gateway policies and cooperative delays expose authored expiry and
ordering mistakes. This is not a claimed nginx flaw or a native QNX nginx port.

```sh
python3 -S -m deadline_lab external-campaign \
  --repetitions 5 --out artifacts/external-campaign
```

Open its generated `report.html`. The checker reads file bytes, and healthy writes
must succeed. The adapter reuses the same repeated reducer as the native workflow.
See [the external target](docs/external-target.md) for individual scenarios.

## Limits

The native effect is an integer-state change in a test process. No physical
actuator, production vulnerability, worst-case latency or safety certification is
claimed. The QEMU run verifies this bounded application contract; it is not a
hardware timing benchmark.

Reduction establishes empirical, grammar-constrained deletion-1-minimality at the
recorded repetitions. It does not prove a globally shortest sequence or exact
schedule replay. Hashes detect corruption and wrong builds, not a dishonest author
fabricating consistent evidence. The native fixture has one pending operation;
concurrent production services need their own adapters and contracts.

A fresh outside developer has not yet reproduced the project. No unseeded defect
in an independent QNX application has been demonstrated.

[Architecture](docs/architecture.md) · [Capture details](docs/host-driven-capture.md) ·
[Native evidence gate](docs/qnx-native-gate.md) · [Entry status](docs/competition-entry.md) ·
[References](docs/references.md) · [MIT licence](LICENSE)
