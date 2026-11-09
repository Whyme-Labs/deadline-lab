# Competition decision gates

Code volume and test counts do not translate into a winning probability.

| Gate | Evidence at v0.3.0 | Decision |
| --- | --- | --- |
| Execute failures rather than narrate them | Compiled C workers; real process lifecycle faults; real HTTP requests and file effects | Achieved locally |
| Convert a failure into a small regression | Shared adapter-neutral reducer; C and external suites; JUnit; bad-candidate negative control | Achieved for bounded authored cases |
| Avoid trivial success by rejecting everything | Healthy probes fail the reject-all control | Achieved locally |
| Avoid success on missing evidence | Integrity, bounded framing, tri-state deletion audit, provenance, incomplete-run and clean-exit checks | Tested for implemented formats |
| Reuse beyond our original fixture | Unmodified nginx backend; independent filesystem observations | Partly achieved on Linux |
| Find an unseeded mistake in an independent QNX application | None demonstrated | Still open |
| Demonstrate QNX-native value | Source-level build, ABI, paired observation, reduction and JUnit acceptance pipeline | Blocked on licensed SDK and target execution |
| Fresh-developer reproduction | ZIP extraction and clean source-only automated check, not a human trial | Human trial still open |
| Demonstrate novel contribution | Focused recovery/ordering-to-regression workflow | Differentiation hypothesis, not established novelty |
| Final submission | Local source and evidence bundle | Public repository, native evidence, codelab and video not completed |

The nginx work is an external validation adapter, not a pivot to a web-server product. The authored gateway intentionally exposes policy mistakes. No nginx vulnerability, unknown production defect or native QNX nginx port is claimed.

The next meaningful gate remains QNX execution. Compile with the real SDK, collect repeated unblock/effect evidence and run the shared reduction path. Do not replace that work with another larger synthetic campaign or a more polished dashboard.

Then ask an unfamiliar developer to reproduce a failure and record the setup cost. A specific unseeded application mistake would strengthen the submission further, but its existence must not be assumed.

Do not claim invention of fault injection, tracing, watchdogs, delta debugging or motor control. Do not call Linux an emulation of QNX. Do not claim universal cancellation, safety, motor efficiency, worst-case latency or durable exactly-once physical effects.

## v0.4 update

Host-driven C collection removes the target Python dependency in the new execution path. Real POSIX process-I/O tests cover collection, framing and direct-child cleanup. The full host-to-QNX acceptance success path, live SSH, an external developer trial and the actual QNX compilation/runtime gate remain open. These local tests are not evidence of native cancellation semantics or hardware safety.

## v0.5 update

The offline handoff, relocation and import transport has been exercised with real
Linux processes. It rejects a changed target executable against the original host
request. Portable records cannot earn a native verdict. No new application bug or
QNX behaviour has been established. The QNX SDK and booted target are now the only
platform inputs needed for the first native capture; live SSH and target Python
are optional. Repeated comparisons, reduction, regression sensitivity and an
independent developer trial remain separate open requirements.
