# Architecture and evidence boundaries

## Local execution path

`Scenario generator -> runner -> compiled C controller -> separate virtual plant -> trace -> independent checker -> reducer -> regression suite`

The runner owns a command bank and launches a new process generation after a kill. The command bank retains original bytes, so a later delivery can contain an old generation. The C worker never changes a command's identity or validity interval. The plant process persists across worker restarts and records observed effects separately from worker responses.

A command carries an ID, authority generation, issuance timestamp, expiry timestamp and signed integer change. The fixture has a two-phase prepare/commit interface so fault orderings can be controlled. A real application would need equivalent integration points or an adapter. This is not transparent instrumentation of arbitrary binaries.

## Contracts

At authorisation, the command must belong to the worker's current generation and lie in the half-open validity interval. An acknowledged cancellation prevents a later effect. A command cannot produce more than one effect within the declared identity model. Payloads must match immutable issued data. The virtual plant's cumulative state must agree with its individual effects.

Every scenario ends with a new, healthy command under the current authority. Exactly one effect is required for that command. Rejecting everything therefore fails progress rather than receiving a misleading safety pass.

An attempt ID associates each observed effect with an independently recorded commit request and worker generation. The checker reconstructs properties from these facts. It does not reuse the C implementation's guard functions, mutation mode or acceptance verdict.

## Time and observation

All local participants use the same host's monotonic clock. The worker records the timestamp immediately before its core authorisation check. The plant separately records when it receives that effect and updates its synthetic state.

The declared expiry property is an **authorisation deadline**. It is not a physical motion deadline. A process can be preempted between authorisation, pipe write and plant observation. A real actuator integration must validate the command at the final effect boundary or account for a measured, justified transport/actuation budget. This prototype does neither.

The virtual plant is an integer state, not a motor, gearbox, thermal or electrical model. The dispenser label exercises the same synthetic endpoint, so it is not evidence of a second independently authored application. No torque, current, energy efficiency, force or physical safety improvement was measured.

## Fault semantics

SIGSTOP/SIGCONT actually pause and resume the spawned C process. The runner waits for an observed stopped state. SIGKILL terminates a spawned process, which is reaped before its replacement starts. No external process can be selected by scenario content.

Delay and acknowledgement loss are explicit test hooks. The lost-ack hook performs the core operation but suppresses the worker response. The observer may still see the effect. A client timeout means unknown completion, not acknowledged cancellation. The runner deliberately does not equate those states.

The PREPARE, COMMIT and ABANDON controls are laboratory interfaces. They do not reproduce the QNX kernel's message scheduling, pulse delivery or resource-manager behaviour. Native QNX evidence must come from the separate target gate.

## Idempotency and crashes

The 512-entry ledger is per worker session. It never evicts applied/cancelled entries to make a test pass. New authority generations fence off old command envelopes after a restart. This does not provide durable exactly-once execution across a full controller/device power failure, nor does it solve reauthorisation of the same logical operation under a new ID or generation.

A real system with an uncertain prior effect must reconcile device state, journal outcomes or use a suitable device-level idempotency mechanism. Automatically retrying with new authority is not implemented as a safe recovery strategy here.

The core marks an operation applied before emitting the effect frame. A subsequent pipe failure is an infrastructure error, not proof that the plant acted. This is intentional: the toy core is not a transactional I/O implementation.

## Evidence integrity

The plant writes sequence-numbered, hash-chained events and a completion record. Missing, modified, reordered or truncated evidence produces INCONCLUSIVE. A separate manifest hashes the scenario, host events, oracle input, worker diagnostics and result. Hash chains detect accidental integrity failures; a malicious writer can recompute them. This is not authentication or a tamper-proof audit system.

The effect record and its timestamp remain trusted instrumentation. We separated the code paths and processes, but did not construct an adversarially independent physical sensor. A dishonest target could fabricate effects. That threat model is outside this experiment.

## Search and reduction

Discovery uses 40 seeds starting at 1000. A held-out seed set uses 40 seeds starting at 100000. The implementation and grammar are unchanged between them. Seeds in the second set were not used to choose the witnesses. This is a limited holdout, not evidence of generalisation to an unknown application.

The generator is mode-blind but uses an authored fault grammar. It does not learn a policy, instrument coverage, perform symbolic execution or infer a specification. The four seeded mutations remove one guard each. Reject-all is an independent negative control.

Delta debugging removes action groups and then audits single deletions. Invalid dependency-breaking candidates cannot become reproductions. Accepted candidates must exhibit the selected property twice. A final five-against-five replay is saved. Deletion-1-minimality is local to the grammar and observed repetitions, not a globally shortest sequence or a guarantee against timing variation.
