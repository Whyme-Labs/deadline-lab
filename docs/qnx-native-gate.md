# Native QNX gate

Status on 9 November 2026: source scaffold only. No QNX compilation or execution took place. The local build helper exited 77 because qcc was absent. The native runner reported NOT_RUN on Linux. The environment record also found no QEMU executable on PATH; this says nothing about a separate remote desktop.

## What the canary checks

QNX documents a distinction between a client wanting to unblock and the server completing or cancelling an operation. With `_NTO_CHF_UNBLOCK`, a client that is already REPLY-blocked does not independently escape `MsgSend` merely because its timeout expires. The kernel sends an unblock pulse and the server must respond according to its operation semantics. [R1, R2]

The canary declares a cancellable, simulated operation with a 150 ms pre-commit delay and a 25 ms client timeout. The reference responds to a valid pending unblock request by cancelling before its simulated effect. An explicitly named `ignore_unblock` mutant ignores that application policy. This is a deliberately faulty example, not a newly discovered QNX flaw, and ignoring a pulse is not universally wrong for every service. [R1, R2]

The receiver uses `rcvid_t`, a union large enough for a pulse and the wire message, and checks message lengths. It queries the kernel's current `_NTO_MI_UNBLOCK_REQ` state through `MsgInfo`, rather than trusting a late pulse to refer to a still-valid operation. It never replies to the pulse itself. `MsgError(rcvid,-1)` is restricted to the pulse-handling path; the pre-commit polling path uses explicit ECANCELED. [R3, R4, R5]

A second healthy call must still create an effect. A timeout that happened while SEND-blocked, before the server received the request, is not valid evidence for the REPLY-blocked unblock scenario. The target script marks missing fault activation INCONCLUSIVE.

## Required access

An appropriately licensed QNX SDP 8 installation and a booted QNX 8 target are required. QEMU is a possible target, not a substitute for a licensed image. This package does not download or redistribute platform components and does not accept license terms on the user's behalf.

The SDK environment must provide `qcc`, `QNX_HOST` and `QNX_TARGET`. The toolchain variant must exist in that SDK, as listed by `qcc -V`. The default is `gcc_ntox86_64`; an AArch64 target requires the corresponding available variant. The development container's Debian Linux tests are not a claim of supported QNX host status.

The target must permit this lab process to create a public channel. QNX documents a public-channel process-manager ability requirement. A failure here is a setup blocker; the scaffold does not escalate privileges or modify the target's security policy. [R2]

The Python native runner is optional convenience and requires Python 3 on the target. The native client and server can also be run manually. The current canary is not wired into the generic fault generator or reducer; that integration is open work.

## Acceptance record

Record the SDK and OS versions, target image provenance, build flags, compiler diagnostics and source revision. Capture actual server process/channel IDs from startup, client observations and server event logs. Repeat the reference/mutant case without editing delays to make a video look successful. Record activation failures and timing variation rather than dropping unsuccessful runs.

The required outcomes are a real observed unblock condition, no cancelled effect in the reference, a visible effect in the deliberately faulty fixture, successful healthy work afterwards and no unresolved client blockage. The external runner bounds both startup and client completion. It kills only its own server process during cleanup.

Run a target-side observer or instrument the actual simulated-effect boundary before claiming the complete independent-observation workflow. The canary log is component instrumentation, not yet the separate observer used by the Linux path. Integrate trace completeness and regression export before treating this as submission-quality native tooling.

## Remaining native engineering

Compile-time API/ABI corrections may still be required. The source has not been syntax-checked using fabricated QNX headers, because that would not establish compatibility. Review disconnect behaviour, queued pulses, resource limits, receipt identifier reuse, simultaneous client requests and response/commit races on the actual target. The current single-pending-slot implementation simplifies concurrency and rejects extra requests as busy.

Do not infer a hard-real-time latency bound, motor safety property, production readiness or verified SDK compatibility from the source alone.
