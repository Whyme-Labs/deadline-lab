# Competition decision gates

The objective is a useful tool with an observable engineering contribution. Code volume and a polished report are not proxies for winning probability.

| Gate | Current evidence | Decision |
| --- | --- | --- |
| Execute faults rather than narrate them | Compiled C workers, real process pause/kill/restart, separate synthetic plant | Achieved locally |
| Find failures without a manually timed video | Mode-blind generated fault sequences expose four seeded defect families | Achieved for authored fixtures only |
| Convert a failure into a useful regression | Reduced witnesses and executable suites with JUnit | Achieved locally |
| Avoid false success from rejecting every command | Mandatory healthy progress control; reject-all fails all 80 campaign histories | Achieved locally |
| Handle missing evidence conservatively | Trace corruption, truncation and loss tests produce INCONCLUSIVE | Achieved for this trace format |
| Demonstrate QNX-native value | Native timeout/unblock canary source with documented semantics | Still blocked on SDK/target execution |
| Show reuse beyond our own demonstration | Two domain labels share the same fixture | Not achieved; independent application needed |
| Demonstrate onboarding value | Automated clean-copy build is useful but not a fresh human user's trial | Human trial still needed |
| Show competitive differentiation | Concrete recovery-to-regression workflow | A hypothesis, not validated novelty or a prize forecast |
| Final submission | Public repository, native evidence, tutorial and demonstration | Not assembled |

## What would materially improve the entry next

First, compile and run the QNX canary on the real platform and connect its evidence to the same checker/reducer interface. The platform-specific result should survive repeated runs and include actual fault activation.

Second, use an independently authored sample application with permission and a documented instrumentation cost. Finding an application mistake beyond our deliberately inserted guards would improve the claim. Failure to find such a mistake is not evidence that one exists.

Third, give a developer unfamiliar with this repository the documented setup and one failing reproduction. Record setup time, missing dependencies, edits and whether they can explain the failure. A ten-minute setup is a proposed goal, not a measurement.

Only then prepare the short demo and codelab. The pitch should show the wrong effect, the small reproduction and the regression result. It must distinguish the fixed example from a universal safety guarantee.

## Claims to avoid

Do not claim invention of fault injection, watchdogs, tracing, delta debugging or motor feedback control. Do not describe the local harness as a QNX emulator. Do not call a seeded defect an unknown production bug. Do not claim the tests prove physical safety or improved motor efficiency. Do not translate fixture detection rates into a probability of winning.
