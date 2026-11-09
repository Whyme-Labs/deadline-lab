# Deadline Lab v0.2.0 implementation checkpoint

9 November 2026. Work performed locally from the verified v0.1.0 archive.

## Decision

The workbench now has a useful independent-target demonstration. It ran against a locally installed nginx server, generated real HTTP traffic and checked actual file changes. Its reducer and regression exporter are no longer tied to the original C controller fixture.

This reduces the risk that the product works only with its original demonstration. It does not establish a prize probability. Native QNX execution, an independently reproduced QNX application mistake and a fresh developer's onboarding trial remain open.

## The concrete new result

An expiry check did not solve request reordering. A held older request was still within its validity period when a newer request changed the target file. When released, the older request overwrote that newer value. The sequence fence rejected this request in the compared implementation.

The separate expiry case let the client time out before releasing a held request. The timeout-only gateway still dispatched the request, and nginx changed the file. The deadline-aware policies rejected dispatch after expiry.

In a response-loss control, the file changed but the client received no acknowledgement before its timeout. The tool recorded the observed effect rather than labelling the timeout as cancellation or rollback. An admitted operation cannot be retracted merely because its response is missing.

These are authored application-contract failures in our gateway policies. nginx is an unchanged independent backend, not a newly discovered vulnerable product. The operations affect disposable files, not actuators. A dispatch deadline is not a hard backend persistence deadline.

## Final independent-target campaign

The final campaign used two scenario families, five parameter seeds each and four policies. It performed 40 scenario executions. These are ten histories against four policies, not forty separate applications.

| Gateway policy | Pass | Fail | Inconclusive |
| --- | ---: | ---: | ---: |
| Timeout only | 0 | 10 | 0 |
| Expiry check | 5 | 5 | 0 |
| Expiry plus sequence fence | 10 | 0 | 0 |
| Reject every request | 0 | 10 | 0 |

Every scenario includes a healthy write. The reject-all implementation therefore fails, even though it cannot produce a stale effect. Each passing fenced run made useful progress.

Evidence location: `evidence/v0.2.0/external-final/summary.json`. Per-run directories contain the scenario, request/observation history, raw file snapshots, server configuration, version, binary hash, process exit status, logs and integrity manifest. The nginx executable is not redistributed.

## Reduction and regression

| Failure | Original actions | Reduced actions | Bad-policy failures | Fenced-policy passes |
| --- | ---: | ---: | ---: | ---: |
| Expired dispatch produces an effect | 7 | 3 | 5 of 5 | 5 of 5 |
| Still-valid old request overwrites a newer one | 6 | 3 | 5 of 5 | 5 of 5 |

The reduced ordering case is simply hold the old request, write the new value, then release the old request. The expiry case is hold, wait for the actual client timeout, then release.

Every accepted reduction was repeated twice. The final records passed a one-action deletion audit. This is local minimality in the declared grammar, not a globally shortest execution or exhaustive search. The two reductions executed 13 and 11 candidate runs. Intermediate candidate directories are temporary; final witnesses and repeated comparisons are retained.

The exported external regression suite met all four expectations, two candidate passes and two negative-control failures. Running the suite with the expiry-only policy as the candidate correctly failed one expectation and produced a JUnit failure. The original eight C-fixture regression expectations also passed after the refactor.

## Shared engine changes

The reducer now receives an adapter runner and scenario validator. It preserves a named violated property, repeats candidate observations and refuses to use an inconclusive run as a failure witness. Explicit execution budgets prevent an unbounded reduction.

The external checker independently validates the file snapshots against request identities, values, sequences and expiry fields from the scenario. Missing files, altered bytes, shuffled observations, changed request identity or unclean target exit cannot produce a passing result.

The external target starts in its own foreground process with an isolated configuration and output prefix. It listens only on loopback and verifies a private startup token before sending writes. The runner does not modify, reload or stop an existing nginx service.

## Native QNX progress and its limit

The QNX server source now emits virtual effects to a separate observer through the same C pipe emitter used by the Linux fixture. It has a graceful termination path and nonzero fatal-error exits. The client records request and reply identity fields.

The native checker cross-checks client results, actual unblock activation, server lifecycle events and independently observed effects. Missing activation remains INCONCLUSIVE. A separate native reduction entry point connects this adapter to the shared reducer and exports a reduced scenario for repeated comparison.

Fourteen local tests exercise the native evidence checker and platform guard using records explicitly labelled synthetic. These tests do not invoke or emulate QNX APIs.

The environment still had no `qcc`, `QCC` or checked QEMU executable on PATH. The native build helper exited 77. The target runner also exited 77 on Linux and recorded NOT_RUN. No QNX headers, images or proprietary binaries were fabricated or redistributed. The source may still need native compilation and runtime corrections.

## Validation

The full Python suite passed 59 tests in this environment, including the optional external target tests. The C tests passed 1,052 core assertions and nine effect-pipe assertions.

Clang AddressSanitizer and UndefinedBehaviorSanitizer completed both C test executables and six process scenarios without observed diagnostics. Clang static analysis reported no diagnostics for the three portable C source files in the executed invocation. The QNX-specific C files were not included in those Linux compile or analysis claims.

All 68 retained final external run bundles passed manifest checks and independently reproduced their saved verdict and property set. Those 68 comprise the 40 campaign runs, four acknowledgement-loss controls, twenty final witness replays and four regression checks. Rechecking evidence is not counted as new execution.

A fresh source-only directory rebuilt the project and passed both verification entry points without package installation or network access. Its 65 source files matched the then-current working source byte for byte. It used the existing nginx installation. The record is `evidence/v0.2.0/clean-source-summary.json`. The progress document and release metadata were added after that copy check; executable source did not change.

No laboratory nginx, plant or controller process remained after the recorded cleanup check.

## Boundaries and unresolved work

The independent observation is a filesystem read of a controlled, single-writer target. Values are distinct so the adapter can associate transitions with requests. It cannot count invisible duplicate writes of an identical value. It does not implement durable exactly-once physical effects, cross-host clock alignment, cross-reboot reconciliation, arbitrary application instrumentation or a physical motor model.

The existing source-only native canary checks one declared cooperative cancellation policy. Cancellation racing with commit still requires a service-specific decision boundary. Finite tests do not prove universal cancellation or worst-case latency.

An attempted libmodbus source retrieval could not complete through this environment's available download path. It was not used or represented as tested. The independent execution instead used the already installed nginx server. This is not a pivot to building a web-server product.

## Next decision gate

Compile and execute the native adapter on an authorised QNX target. Require actual unblock activation, repeated independent effect observations and successful regression export. Then have a developer unfamiliar with this work reproduce a failure. Those results should determine submission confidence. More synthetic volume or dashboard polish cannot replace them.

The source, documentation and evidence remain local. No GitHub push, remote CI, package installation, hardware purchase or deployment occurred.

Primary interface references are listed in `docs/references.md` and `docs/external-target.md`. Experimental claims come from the included run evidence, not those documentation sources.
