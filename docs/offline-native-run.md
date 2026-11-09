# Run the QNX capture without granting remote access

## Status

The prepare, relocate, run and import workflow has been exercised with real Linux
collector processes. The application programs in that rehearsal are explicitly
portable process-I/O fixtures. They do not implement QNX IPC. A complete genuine
QNX build, target capture and native import remain unexecuted.

This is an additional deployment route, not a new safety feature or a substitute
for the native acceptance gate. The existing live SSH workflow remains available.

## What is needed

A development computer needs an authorised QNX SDP 8 SDK, CMake and Python 3.10 or
newer. The target can be a supported board or an authorised QNX VM. On the target,
the new wrapper requires `/bin/sh`, `mkdir` and the normal runtime required by our
own compiled executables. No target Python, pip, compiler, SSH daemon or target
source tree is needed by this route.

QNX's [licence codelab](https://qnx.github.io/codelabs/get-non-commercial-qnx-license/index.html)
explains the account and licence request. Follow the
[official QEMU target guide](https://www.qnx.com/developers/docs/qnxeverywhere/com.qnx.doc.target_images/topic/qsti_qemu/about.html)
to install and boot an appropriate image. Use the licence appropriate for the
activity. This project does not accept licence terms, obtain SDK files, change
security abilities or provision a machine. Do not include licence keys or vendor
SDK/runtime components in this project's public artifacts.

## Prepare on the development host

Source the existing authorised SDK environment. From the project directory:

```sh
./scripts/build-qnx.sh --out artifacts/qnx-build
python3 -S -m deadline_lab.offline prepare \
  --bin artifacts/qnx-build/build \
  --mode reference --out artifacts/reference-ticket
```

Preparation refuses missing binaries, a missing native build record, a source
revision mismatch, changed binary bytes and existing destination directories.
It cannot make a Linux build count as QNX simply by changing a command-line flag.
The portable test entry point exists in the test API only, not in this CLI.

The host keeps `artifacts/reference-ticket/request.json`. Do not replace it with
a request returned by the target. Its nonce, source identity, binary hashes and
metadata hashes identify the intended run. Keep the request and returned capture
private until checking whether their paths contain sensitive information.

Copy only the `artifacts/reference-ticket/target` directory through an approved
file transfer or removable medium. It contains our four executables, two build
records and `run-target.sh`. There are no SDK components. Preserve executable
permissions when transferring the files. The folder can be relocated. The
wrapper resolves its own location rather than depending on a host-side path.

## Execute on the QNX target

From the transferred target directory, select a new result directory:

```sh
./run-target.sh /tmp/deadline-reference-001
```

The result directory must not exist. The wrapper will not overwrite it or follow
an already existing result-directory symlink. It captures `capture.stdout`,
`capture.stderr` and `capture.exit`. A nonzero exit must be retained. Do not edit
it to zero or discard diagnostics. Interrupted or incomplete captures do not pass.

This runs only the virtual-effect demonstration processes. Never connect this
fixture to physical machinery or a motor controller.

## Import on the host

Bring the result directory back through any approved transfer. The importer does
not contact the target:

```sh
python3 -S -m deadline_lab.offline ingest \
  --request artifacts/reference-ticket/request.json \
  --results /path/to/returned/deadline-reference-001 \
  --out artifacts/reference-import
```

The importer checks framing, size bounds, the original request nonce, compiled
binary identities, exact build/source records and clean completion. It then uses
the same native evidence checker as the live collector. The observer records,
actual native unblock activation and healthy progress remain mandatory.

The host records that it imported files, not that it personally observed or
reaped a remote process. The target collector's own direct-child cleanup records
remain part of the evidence. Hashes catch mismatched or accidentally corrupted
artifacts. They do not authenticate a malicious party that fabricates a complete
consistent evidence set. Repeating the same valid request can produce another
capture; the nonce is not a durable single-use ledger or a trusted time source.

Prepare an independent `ignore_unblock` ticket to test the negative control:

```sh
python3 -S -m deadline_lab.offline prepare \
  --bin artifacts/qnx-build/build \
  --mode ignore_unblock --out artifacts/negative-ticket
```

The expected negative result is an application `FAIL` when the declared native
unblock-before-effect ordering is actually observed. Lack of that activation is
`INCONCLUSIVE`, not a successful negative-control test.

One imported case does not close the native acceptance gate. Repeated paired
comparisons, reduction, regression export and a regressed-candidate sensitivity
check remain required. The existing fully automated acceptance workflow uses a
live collector connection. This first offline route executes and imports one
case at a time. It does not claim an automated offline reduction campaign.

## Rehearse the transfer workflow locally

```sh
./scripts/verify-offline.sh
```

This builds the portable collector, runs the offline tests, then retains four
real Linux captures and four additional modified/reassociated import checks. A
successful portable import is labelled `TRANSPORT_ONLY`, never `PASS` for QNX.
The test covers a relocated folder, a changed executable, a stalled child,
truncated files, a missing completion record, diagnostics and a different host
request. Intermediate binary handoffs are temporary and removed afterward.

## Remaining blocker

This environment has no authorised QNX SDK or booted QNX target. Native execution
still requires those two inputs. SSH is no longer a requirement for collecting
and importing the first native case. Documentation checks and portable runs do
not replace genuine SDK compilation and native runtime observations.
