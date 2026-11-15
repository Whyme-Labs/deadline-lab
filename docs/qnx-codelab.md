# From a QNX timeout to a replayable regression

This codelab reproduces an authored cancellation mistake on QNX 8. You will run
both implementations, observe their effects, reduce a failing sequence and replay
an exported regression. It uses a virtual integer-state effect, with no hardware
actuator. Allow about 20 minutes once your licensed SDK and target are ready.
SDK installation and account setup take additional time.

## 1. Prepare the development host and target

You need Python 3.10+, CMake 3.16+, SSH, and your own licensed QNX SDP 8 SDK.
Follow [QNX's licence and installation guide](https://www.qnx.com/getqnx).
For a Mac, QNX documents a
[Linux-container build environment](https://qnx.software/en/blog/2026/how-to-use-macos-to-develop-for-qnx).
Run the build and Python commands below inside that Linux environment. Keep the
SDK on case-sensitive Linux storage, such as a Docker named volume. A
case-insensitive shared Mac folder caused conflicting SDK filenames during our
setup. QNX Software Center's installation verification passed after repair on a
Linux volume.

Use a booted QNX 8 target and an SSH account allowed to create the demonstration
channel. The recorded target was QNX 8.0.0 AArch64 on QEMU 10.0.0, with two CPUs
and 512 MiB RAM. No target Python is required. QNX's
[QEMU target guide](https://www.qnx.com/developers/docs/qnxeverywhere/com.qnx.doc.target_images/topic/qsti_qemu/about.html)
is another starting point; select the compiler variant that matches your image.

Our AArch64 image used the SDK's `mkqnximage` tool. In QNX Software Center install
the QEMU/virt target package and the VirtIO driver group in addition to SDP 8.
The corresponding package IDs are `com.qnx.qnx800.target.qemuvirt` and
`com.qnx.qnx800.target.driver.virtio`. The latter supplies block, console and
startup components needed by this image. After sourcing your SDK environment,
run in a new image directory, with your SSH public key at the selected path:

```sh
mkqnximage --type=qemu --arch=aarch64le --graphics=no --python=no \
  --cpu=2 --ram=512M --ssh-ident=/path/to/your/public-key.pub \
  --sshd-pregen=yes --hostname=deadline-qnx --noprompt
```

Keep `ifs.bin`, `disk-qemu` and `disk-qemu.vmdk` from the same generated output
set together. We used this invocation from that folder on the Mac:

```sh
qemu-system-aarch64 \
  -machine virt-4.2 -cpu cortex-a57 -accel tcg -smp 2 -m 512M \
  -drive file=disk-qemu.vmdk,if=none,id=drv0 \
  -device virtio-blk-device,drive=drv0 \
  -netdev user,id=net0,restrict=on,hostfwd=tcp:127.0.0.1:55022-:22 \
  -device virtio-net-device,netdev=net0 \
  -kernel ifs.bin -nographic -serial mon:stdio \
  -object rng-random,filename=/dev/urandom,id=rng0 \
  -device virtio-rng-device,rng=rng0
```

Create a local SSH alias `qnx-lab` pointing at your target. For this Mac-hosted VM,
the Linux container reaches `host.docker.internal` on port `55022`; an SSH client
on the Mac uses `127.0.0.1`. Pin the SSH host key against the key generated for
your image or a fingerprint verified through the target console. The project's
collector requires strict host-key checking and batch authentication. Confirm:

```sh
ssh qnx-lab uname -a
```

Expected: QNX 8 and the architecture of your selected image. Do not replace a
failed connection with disabled host-key checks.

## 2. Build the project

Clone the public source and select the release:

```sh
git clone https://github.com/Whyme-Labs/deadline-lab.git
cd deadline-lab
git checkout v0.6.0
```

Source your installed `qnxsdp-env.sh`. Then build for AArch64:

```sh
./scripts/build-qnx.sh --variant gcc_ntoaarch64le --out artifacts/qnx-build
```

Expected: `status: COMPILED` and `qnx_compiled: true`. The tested compiler was
qcc 12.2.0. The output records compiler commands, source hashes and ELF identities.
Compilation alone does not mark the application behavior as passed. For an x86_64
image use `--variant gcc_ntox86_64`; this release's runtime evidence is AArch64.

## 3. Deploy only the project files

```sh
ssh qnx-lab 'mkdir -p /tmp/deadline-bin'
scp -p artifacts/qnx-build/build/dl-capture \
  artifacts/qnx-build/build/dl-qnx-server \
  artifacts/qnx-build/build/dl-qnx-client \
  artifacts/qnx-build/build/dl-qnx-abi \
  artifacts/qnx-build/build/build-record.json \
  artifacts/qnx-build/build/source-manifest.json \
  qnx-lab:/tmp/deadline-bin/
```

Keep the host source revision unchanged between build and capture. The target
needs its normal QNX C runtime, not the source tree, CMake or Python.

## 4. Observe a passing reference and a failing policy

```sh
python3 -S -m deadline_lab.capture examples/native/unblock.json \
  --ssh qnx-lab --bin /tmp/deadline-bin --mode reference \
  --out artifacts/reference

python3 -S -m deadline_lab.capture examples/native/unblock.json \
  --ssh qnx-lab --bin /tmp/deadline-bin --mode ignore_unblock \
  --out artifacts/negative
```

Expected: the reference is PASS; the negative is FAIL for `cancel_before_effect`
and exits 1. A failure is the expected result for that deliberately flawed policy.
Read each `result.json`, `server.jsonl` and `effects.raw.jsonl`.
The checker requires the observed unblock request to precede the effect. A run
that does not activate that ordering is INCONCLUSIVE. It does not invent a defect
from a timeout alone.

In `qnx/client.c`, `TimerTimeout` bounds the client operation. In `qnx/server.c`,
the reference handles the unblock notification and checks `MsgInfo` before the
virtual commit. The collector observes effect frames through a separate pipe.
A later healthy request must still produce its expected effect.

## 5. Reduce, export and test the regression

```sh
python3 -S -m deadline_lab.native_workflow accept \
  --collector --ssh qnx-lab --bin /tmp/deadline-bin \
  --out artifacts/native-acceptance
```

The workflow runs five reference/negative pairs, independently rechecks their
captures, reduces the failure, exports a suite, replays it five times and then
substitutes the flawed candidate once. Inspect:

- `acceptance.json`: `ACCEPTANCE_COMPLETE` with all five gate booleans true.
- `reduction.json`: recorded candidate outcomes and deletion audit.
- `regressions/unblock.json`: the reduced timed call.
- `regression-replay-0/junit.xml`: passing regression and sensitivity expectations.
- `regressed-candidate/junit.xml`: an expected failure proving the suite detects the policy regression.

Our recorded sequence shrank from five scripted calls to one timed call with
200 ms work and a 30 ms timeout. The collector adds a healthy call separately.
This is empirical deletion-1-minimality within the scenario grammar, not a proof
of the shortest possible concurrent execution.

Replay the included reduced suite with a candidate build:

```sh
python3 -S -m deadline_lab.native_workflow regress regressions/native/suite.json \
  --collector --ssh qnx-lab --bin /tmp/deadline-bin \
  --out artifacts/replay --sensitivity
```

Use a new output directory on every run. Recheck saved canary captures offline:

```sh
python3 -S -m deadline_lab.native_gate artifacts/native-acceptance/canary
```

## Troubleshooting and limits

If compilation reports NOT_RUN, check the sourced SDK environment and licensed
installation. If the generated image cannot find a VirtIO component, install the
matching target driver group. If disk mounting fails after copying an image,
compare the VMDK descriptor's sector count with the flat disk's size; copying a
new disk with an old descriptor caused this exact failure during our setup.

If capture reports a source or binary mismatch, rebuild and deploy the complete
six-file set. Preserve failing captures and use a fresh output path for retries.
Missing evidence, an unobserved unblock, or an interrupted transport stays
INCONCLUSIVE. A valid result is never obtained by editing the summary.

For a target without SSH, use the [offline prepare/run/import route](offline-native-run.md).
The example checks an authored virtual-effect contract. It does not establish a
QNX vulnerability, physical safety, hard-real-time performance, or cancellation
semantics for every service. Production adapters must define their own effects,
commit boundary, concurrency and recovery rules.
