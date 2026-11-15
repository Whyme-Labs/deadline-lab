# QNX Global Hackathon entry

Status on 16 November 2026. Native validation and the public repository are ready.
The Devpost draft exists; a final submission receipt has not yet been recorded.

## Category and required materials

Category: Developer Tooling & Host Tools. The
[official rules](https://qnx.devpost.com/rules) close submissions on 15 December
2026 at 14:00 EST, which is 16 December at 03:00 in Malaysia. Requirements include
public open-source code, build/run instructions, a feature description and a
public YouTube demo under three minutes. The codelab bonus uses the tutorial URL.

- Source: https://github.com/Whyme-Labs/deadline-lab
- Licence: MIT, detected by GitHub.
- Build/run guide and codelab: [qnx-codelab.md](qnx-codelab.md).
- Version: 0.6.0, with source and raw native evidence in the GitHub release.
- Demo and submitted entry: pending publication and readback.

## What was built

Deadline Lab checks whether a timeout, restart or retry produces an effect that
violates a stated application contract. It runs compiled test processes, records
effects through a separate observer, reduces reproducible failures and exports
regressions with JUnit output. Healthy probes prevent a reject-everything policy
from passing. Missing or inconsistent observations remain inconclusive.

The QNX path uses `TimerTimeout`, message passing, unblock pulses and `MsgInfo`.
A C collector runs on the target; Python analysis stays on the host. An additional
offline route pins source and binary identities in a host request, then imports
returned capture files. The test application intentionally contrasts a reference
cancellation policy with `ignore_unblock`.

## Verified results

On 16 November 2026 the release executable source compiled with QNX SDP 8,
qcc 12.2.0, variant `gcc_ntoaarch64le`. It executed on a QNX 8.0.0 AArch64
`QEMU_virt` target with two CPUs and 512 MiB RAM.

- All 159 Python tests passed in the Ubuntu 24.04 validation container.
- The three C programs passed on Linux and on QNX: 1,052 core assertions,
  nine effect assertions and four SHA-256 known-answer vectors.
- Linux core, nginx, collector and offline-transfer workflows passed.
- Native acceptance completed five reference/negative pairs with all ten
  expectations met. Offline rechecking on macOS accepted the raw canary captures.
- Native reduction shrank five scripted calls to one timed call, with a separate
  healthy call. Eight candidate executions completed without an inconclusive
  candidate. This is grammar-constrained deletion-1-minimality.
- Five exported regression replay pairs passed. Substitution of the flawed
  candidate produced the expected failing regression.
- The offline route completed a genuine native reference/negative pair, with
  verified provenance and healthy progress in both imports.

The evidence archive preserves captures, build records, source manifests, effect
observations, reduction details and JUnit files. Release packaging independently
rechecks the native canary and matches it to the current executable source before
recording `NATIVE_CANARY_VERIFIED`.

## Boundaries and future work

All demonstrated defects are seeded in our application fixture or gateway
policies. nginx is an independently authored Linux backend, not the subject of a
claimed nginx vulnerability. The QNX test is a virtual-effect contract, not a QNX
vulnerability, physical actuator test, safety certification or timing benchmark.

No independent developer reproduction or unseeded bug in an independent QNX
application has been demonstrated. Both remain useful next experiments and are
not formal entry requirements. AI assistance from ChatGPT and OpenAI Codex was
used for code, documentation, investigation and test execution and is disclosed
in the submission.
