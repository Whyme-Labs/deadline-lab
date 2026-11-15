# QNX Global Hackathon entry preparation

Checked on 15 November 2026. This is a preparation record, not a submission receipt.

## Deadline and category

The [official rules](https://qnx.devpost.com/rules) close registration and submission
on 15 December 2026 at 14:00 US Eastern Standard Time. That is 16 December 2026 at
03:00 in Malaysia, UTC+8. The deadline has not passed.

Enter **Developer Tooling & Host Tools**. The rules allow tools running on Windows,
macOS or Linux when they meaningfully support software targeting QNX 8.0. Native
QNX execution is the next engineering milestone for this project's cancellation
demonstration; it is not a blanket requirement that every eligible host tool must
itself execute on QNX.

The required submission materials are a public source repository with a detectable
open-source licence, build/run instructions naming QNX version, toolchain and target,
a feature description, one selected category, and a public YouTube demonstration
shorter than three minutes. Reviewers must be able to verify the QNX connection.
See the [submission requirements](https://qnx.devpost.com/).

An independent developer trial and discovery of an unseeded application mistake
would strengthen the entry. They are project quality goals, not additional formal
entry requirements. A codelab is required only when entering that bonus category.

## Current evidence

The recovered v0.5.0 archive has 8,616 matching file digests. Its source history ends
at `cfca84f4ab5497f8b5bda07cd5850c480414653e`. Fresh execution in an Ubuntu 24.04
Linux/amd64 container on an Apple Silicon Mac passed:

- All 158 Python tests and all three C test programs.
- Eight core regression expectations and four nginx regression expectations.
- Sixteen collector campaign expectations.
- Eight offline-handoff expectations, comprising four collector executions and
  four additional import checks.

These results test Linux processes, authored failure policies and evidence handling.
They do not establish QNX compilation, native timeout/unblock behavior, a production
vulnerability, physical actuator safety, or an outside developer's reproduction.

## Entry text draft

**Name:** Deadline Lab

**Tagline:** Turn recovery and ordering failures into small, replayable regression tests.

**Problem:** A timeout does not establish that an operation had no effect. Recovery
code can also accept expired commands, reuse a command after restart, or apply a
retry twice. Developers need short reproductions backed by observed effects.

**What it does:** Deadline Lab launches test processes, injects bounded failures,
observes effects through a separate process or channel, and checks the observations
against an explicit contract. It reduces a reproducible failing sequence and exports
a regression suite with JUnit output. Missing or inconsistent evidence remains
inconclusive. A healthy-operation check prevents a reject-everything implementation
from passing.

**QNX integration:** The native client/server source uses QNX message passing,
`TimerTimeout`, unblock pulses and message information. A C collector is designed
to run on the target while Python analysis stays on the host. An offline handoff
pins source and executable identities and imports returned captures without target
Python or SSH. This native integration has not yet compiled or run on QNX. Replace
this status only after retaining successful genuine build and runtime evidence.

**Current results:** The Linux controller, nginx adapter, collector and offline
transport have passed the checks listed above. The deliberately flawed application
policies are ours. nginx is an independent backend, not the subject of a claimed
nginx vulnerability.

Do not submit this draft as a completed native demonstration. Add the exact QNX
release, compiler variant, target, source revision, evidence paths and actual demo
URL after the native milestone passes.

## Demonstration recording plan

Target duration: 2 minutes 40 seconds. Record actual program output, with a separate
screen identifying the platform and source revision.

| Time | Footage and explanation |
| --- | --- |
| 0:00–0:20 | Introduce the timeout-versus-effect problem and the developer workflow. |
| 0:20–0:40 | Show the genuine QNX build record and running target identity. |
| 0:40–1:15 | Execute the flawed native candidate; show the unblock observation and independently observed effect. |
| 1:15–1:45 | Run reduction and inspect the shorter failing sequence. |
| 1:45–2:15 | Replay the reference and flawed candidates; show passing/failing regression output. |
| 2:15–2:40 | Show the repository and reproduction command; state the virtual-effect and evidence limits. |

Only record the native sections after they work. If an outcome is inconclusive,
resolve its cause and rerun instead of narrating it as a successful result.

## Next steps

1. Create and verify a myQNX account, then request and deploy the free non-commercial
   QNX Everywhere licence at [Get QNX](https://www.qnx.com/getqnx).
2. Install QNX Software Center, QNX SDP 8 and its Linux host tools. QNX documents a
   [Docker build route for macOS](https://qnx.software/en/blog/2026/how-to-use-macos-to-develop-for-qnx).
   The local Linux validation image is not a licensed QNX SDK installation.
3. Build with `scripts/build-qnx.sh` and boot a compatible licensed QNX target.
   Follow [the native handoff](native-handoff.md) and [collector workflow](host-driven-capture.md).
4. Complete repeated native comparisons, reduction, regression export and the
   intentionally regressed-candidate check. Preserve original logs and binary hashes.
5. Publish the verified source with the MIT licence and reproducible instructions.
6. Record and publish the demonstration to YouTube, sign in to Devpost, complete the
   entry, and retain the final submission confirmation.

No submission, registration, native success or licence activation is established
by this document. Verify each in its owning system before updating the status.
