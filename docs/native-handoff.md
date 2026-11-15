# Native QNX handoff

The v0.6.0 native acceptance workflow ran on QNX 8 AArch64 on 16 November 2026.
The [codelab](qnx-codelab.md) gives the build, deployment and verification commands.
The [host collector](host-driven-capture.md) keeps Python off the target, and the
[offline route](offline-native-run.md) can transfer captures without SSH.

Use an appropriately licensed QNX SDP 8 SDK on the development host and an
already booted compatible QNX target. The tested compiler is qcc 12.2.0 with
`gcc_ntoaarch64le`. The build helper also accepts `gcc_ntox86_64`; this release
does not claim a native x86_64 runtime test.

The build directory contains the project executables plus `build-record.json`
and `source-manifest.json`. Transfer the six collector files listed in the
codelab and retain the same host executable source revision. The capture checks
actual QNX identity, ABI fields, binary hashes, raw virtual effects, unblock
activation and clean completion. A relabelled Linux fixture cannot close the gate.

The legacy on-target Python route remains available for targets with Python 3.10+:

```sh
./scripts/verify-native.sh --bin /path/to/qnx-build/build \
  --out artifacts/native-acceptance
```

That legacy route needs the source tree and Python on the target. The v0.6.0
recorded acceptance uses the C collector over SSH instead.

The application contract is cooperative cancellation before a virtual commit.
Neither a timeout nor a passing canary proves rollback, universal cancellation,
hardware timing bounds or physical safety. An outside developer reproduction
and an independent QNX application adapter remain future work.
