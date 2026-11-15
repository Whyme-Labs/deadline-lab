# Native QNX gate

**v0.6.0 status, 16 November 2026:** the genuine QNX SDP 8 build and QNX 8 AArch64 collector acceptance completed, including repeated comparisons, reduction, regression replay and rejection of the regressed candidate. See the [codelab](qnx-codelab.md) and [release evidence](https://github.com/Whyme-Labs/deadline-lab/releases/tag/v0.6.0).

## Historical v0.3.0 design notes

Current entry points and provenance requirements are in [native-handoff.md](native-handoff.md). At v0.3.0 the native path was uncompiled and unexecuted. The historical v0.2 source design below explains the API choices; its old default `build-qnx` directory is superseded by the explicit build-output directory selected by the current helper.

The offline checker now requires the observed unblock to precede any effect before evaluating the intended cancellation property. A commit preceding the unblock is INCONCLUSIVE for this specific test, not evidence of a cancellation defect. A transport timeout alone still does not establish cancellation.

Native-origin bundles must include the actual build record, source manifest and ABI observation. The native gate requires five paired, rechecked runs with matching source/binary identities, positive healthy progress, and a detected omitted-cancellation control. Synthetic records cannot close it.

The reducer's deletion audit is tri-state. Missing observations can preserve a reproducible failure witness while leaving minimality unknown. It no longer silently treats unknown as a non-failing neighbour.

---

# Native QNX gate

Status on 9 November 2026, v0.2.0: native source and integration only. The build helper and target runner both exited 77 here. No QNX compile, target boot or native cancellation observation is claimed.

## Platform-specific question

QNX documents a distinction between a client trying to unblock and the server completing or cancelling a received operation. With `_NTO_CHF_UNBLOCK`, a REPLY-blocked client does not necessarily escape `MsgSend` merely because its timeout expires. The server receives an unblock pulse and must handle its operation according to the service's contract. [R1, R2, R3]

The source canary specifies a cancellable virtual operation with a 150 ms pre-commit delay and a 25 ms client timeout. The reference intends to cancel a pending operation before its virtual effect when the kernel reports an unblock request. The `ignore_unblock` variant deliberately omits that application policy. Ignoring a pulse is not universally incorrect for every QNX service, and the example is not an operating-system vulnerability.

## Changes since v0.1.0

The shared C effect-pipe emitter is used by the Linux worker and the QNX server source. A separate observer process records virtual state transitions. Native success cannot be inferred only from the server's own `effect` log or its reply.

The source runner now requires a clean server shutdown, complete observer trace, positive healthy operation and actual unblock activation. It checks client identity and reply ABI fields. The server source has a graceful termination path and nonzero fatal-error exits.

The native adapter exposes the same scenario-runner interface as the shared reducer. `scripts/qnx-reduce.py` will reduce and replay a genuine native failure once the required target exists. That connection is implemented in source; it has not been executed natively.

The offline checker has fourteen local fixture/guard tests. The fixtures explicitly say `synthetic-unit-test`, never `native-qnx`. They validate record handling, not the correctness of the QNX API calls.

## Build and execute

On a supported development host, obtain an appropriately licensed QNX SDP 8 environment through the official route, source its environment and run:

```sh
./scripts/build-qnx.sh
```

The SDK must provide `qcc`, `QNX_HOST` and `QNX_TARGET`. The default variant is `gcc_ntox86_64`; use an SDK-supported AArch64 variant for that target. The source package does not accept licence terms, download proprietary components or fabricate headers.

On a booted QNX target with Python 3, copy this source package and its correctly built binaries, then run:

```sh
python3 -S scripts/qnx-canary.py --bin ./build-qnx --out native-results --repetitions 5
python3 -S scripts/qnx-reduce.py examples/native/unblock.json \
  --bin ./build-qnx --out native-reduction
```

The second command is only useful after the first produces genuine, repeated native observations. A non-QNX host returns NOT_RUN. Missing native binaries also return NOT_RUN. Neither is a passed test.

## API details to verify on target

The receiver uses `rcvid_t`, a union large enough for a pulse and message, and checks message lengths. It checks the current `_NTO_MI_UNBLOCK_REQ` state with `MsgInfo` rather than treating a queued pulse as an unconditional cancellation of a reused receipt identifier. A pulse itself never receives `MsgReply`. `MsgError(rcvid,-1)` is restricted to handling an unblock pulse; the pre-commit path uses ECANCELED. [R3, R4, R5]

Public-channel permissions must already be authorised. No escalation or security-policy modification is attempted. [R2]

The single-pending-request server is intentionally small. Real target work still needs ABI/compiler corrections, timer/signal observations, disconnect and identifier-reuse cases, evidence-loss behaviour, and concurrency review. The local Linux tests do not establish any of these properties.

Checking for a cancellation request and committing an effect are not a universal atomic operation. A cancellation that races with commit needs an explicit decision boundary and application semantics. The wide-delay canary is a bounded test, not a proof that every cancellation beats every physical action.

## Acceptance evidence

Record the SDK version, target OS/image, toolchain variant, compiler output, source and binary hashes, public-channel setup, client results, actual kernel-unblock observations, observer effects and clean shutdown. Require all repeated reference/mutant comparisons to activate the intended condition. A SEND-block timeout before server receipt is INCONCLUSIVE for a REPLY-blocked cancellation test.

Use the recorded native data to decide whether to proceed. Do not infer a hard-real-time bound, physical motor performance or platform compatibility from source-only integration.

References R1 through R7 are in `docs/references.md`.
