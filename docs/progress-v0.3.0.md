# Deadline Lab v0.3.0 checkpoint

9 November 2026. Local continuation of the verified v0.2.0 archive.

## What this milestone delivers

The local workbench is more reliable, the source-level native acceptance pipeline is connected, and the distributable archive now verifies its own completeness. The actual QNX compilation/execution milestone remains blocked. No QNX compiler, target, physical actuator or outside developer trial was available in this session.

The work deliberately focused on the test tool and the native handoff rather than adding another large synthetic campaign. Three regressions were reproduced in the prior workbench and corrected. A separate packaging omission was also repaired. None is a newly discovered QNX or nginx vulnerability.

## Reproduced findings

| Finding in the previous implementation | Recorded before/after result | Correction |
| --- | --- | --- |
| A readiness pipe became readable after only a partial greeting | The old select-then-readline pattern remained blocked after 150 ms. The new reader returned at its declared timeout while retaining partial input | Deadline-bounded framing, explicit EOF/size/encoding errors and actual child cleanup tests |
| An inconclusive deletion test was treated as evidence that a witness was minimal | The previous reducer reported deletion-1-minimal=true. The same synthetic runner outcomes now yield minimality_status=INCONCLUSIVE and deletion_1_minimal=null | Explicit outcomes and a per-deletion audit; a reproducible witness can coexist with unknown minimality |
| The native checker saw an unblock only after an effect had already committed | The previous offline checker reported a cancellation failure. The same labelled synthetic evidence now returns INCONCLUSIVE for the intended pre-commit experiment | Establish the requested ordering before accusing the implementation of failing the cancellation policy |
| The documented QNX build helper was absent from the v0.2.0 ZIP | Archive inspection found it missing, while its original Git history contained it | Restore the helper; verify source selection, tracked-file completeness, archive readback and executable modes |

The first finding uses real local pipes. A separate test starts an actual child that writes a partial greeting, confirms the timeout, and kills/reaps that owned child. The second and third use explicitly synthetic outcomes/evidence to test the workbench's reasoning. They are not QNX API emulation or native observations.

The timing above demonstrates a blocking-versus-bounded-read difference under this local test. It is not a hard-real-time latency claim.

The standalone reproduction script reads the exact prior ZIP, checks its SHA-256, loads the prior modules in an isolated temporary directory, and compares their output with the current implementations. Raw records are in `evidence/v0.3.0/reproducible-defects`. The package-omission record is `inherited-package-audit.json` in the same evidence parent.

## Native build-to-regression handoff

The new host build helper is independent of the caller's working directory. It inspects the SDK prerequisites, captures configuration and compiler logs, records the source identity, checks the output ELF architecture, and places provenance next to our own binaries. Missing prerequisites produce NOT_RUN with exit 77.

A new native ABI probe records actual OS and message-structure metadata. The source has the real-QNX-SDK guard. It was not compiled with fake headers or substituted Linux definitions.

On an authorised QNX target, the implemented acceptance command is designed to:

1. Verify the binary/source identities and native ABI observation.
2. Run five paired reference and omitted-cancellation comparisons.
3. Independently re-evaluate every case, including real unblock activation, event order, observer effects and healthy progress.
4. Reduce a native failure with the shared reducer and require a conclusive deletion audit.
5. Export a native regression suite with JUnit, replay its comparison five times, and deliberately reject a regressed candidate.

The native acceptance gate rejects a success-only summary, synthetic evidence, missing repetitions, mixed source/binary identities and missing activation. The unit tests intentionally try these cases. Those checks do not make the source an executed QNX implementation.

The complete native success path remains untested. Current evidence proves that Linux is refused, prerequisites are reported, malformed evidence is rejected and the portable components work. Real SDK compilation may still expose errors; actual target scheduling, permissions, timeout semantics and disconnect handling still need observation.

## Validation performed here

| Check | Result |
| --- | --- |
| Python unit/integration tests | 91 passed, including optional locally installed nginx tests |
| Portable C contract assertions | 1,052 passed |
| C effect-pipe assertions | 9 passed |
| Sanitized C test executables | Both passed with no observed diagnostics |
| Sanitized process scenarios | Six real-process scenarios returned their expected reference/negative-control outcomes, with empty stderr |
| Portable C static analysis | No diagnostics in the executed Clang invocations |
| Original C regression suite | All eight expectations met |
| External regression suite | All four expectations met |
| External reduction revalidation | Expiry case reduced from seven to three actions; reordering case from six to three. Both deletion audits were conclusive |
| Final reduced-case replays | Five bad/good comparisons per family reproduced all expected outcomes |
| Offline evidence recheck | 480 historical C runs, 68 historical external runs and 36 newly retained external runs matched their saved verdict/property sets |
| Native build and execution | NOT_RUN, exit 77. No native compilation or execution counted |

The external revalidation campaign used two histories against four policies, giving eight main executions. The 36 retained external bundles also include four acknowledgement-loss controls, twenty final witness replays and four regression checks. Reducer candidate trials are counted separately in the reduction records. None of these counts represents independent applications, a general bug-detection rate or a prize probability.

The 584 offline rechecks are inspections of recorded data, not 584 additional executions. The old v0.1 and v0.2 evidence remains explicitly historical.

## Fresh-package validation

A source-only ZIP is extracted into a new directory with spaces in its path. Its complete source manifest is checked. The archived native build helper must be present and executable. The local and external verification entry points are run there without reusing a prior build directory, downloading packages or installing dependencies. The native helper is invoked from a different working directory and is required to report missing prerequisites rather than a missing script or a native pass.

The evidence is `evidence/v0.3.0/clean-source-summary.json` plus its logs. This is an automated clean-package trial, not an unfamiliar human developer's onboarding trial.

## Reproduce locally

```sh
./scripts/verify-local.sh
./scripts/verify-external.sh
```

The second command needs an existing nginx installation with DAV support. It starts its own loopback-only instance and writes only to its own output tree. It does not operate an existing nginx service.

To reproduce the before/after workbench findings with the prior delivered archive:

```sh
python3 -S scripts/reproduce-harness-regressions.py \
  --prior-archive /path/to/deadline-lab-v0.2.0.zip \
  --out artifacts/harness-regressions
```

For the real native build and acceptance commands, see `docs/native-handoff.md`. Neither helper obtains a licence, changes target security policy or provisions infrastructure.

## Decision

The local reliability and release-handoff work is complete for this checkpoint. The evidence does not justify calling the entry prize-ready. A licensed QNX SDP 8 environment and an authorised booted QNX target remain the next hard dependency. After native acceptance, an independent developer must reproduce a useful failure before we can claim that this saves other developers time.

No GitHub push, remote CI, purchase, cloud deployment, licence acceptance, hardware operation or alteration of the user's other projects occurred. The source and evidence remain local.
