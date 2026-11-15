# Competition decision gates

Status on 16 November 2026 for v0.6.0. Test counts do not establish a winning probability.

| Gate | Evidence | Status |
| --- | --- | --- |
| Execute failures | Compiled C workers, process faults, HTTP/file effects | Demonstrated |
| Observe QNX cancellation behavior | Genuine QNX 8 target, independent effect pipe, five paired comparisons | Demonstrated for our bounded fixture |
| Reduce and export | Five native scripted calls to one; JUnit; five paired regression replays | Demonstrated |
| Reject a broken candidate | Deliberately regressed candidate fails the exported suite | Demonstrated |
| Require healthy progress | Separate healthy call in native runs; reject-all controls in Linux | Demonstrated |
| Reject incomplete evidence | Strict framing, provenance, raw-record rechecks and tri-state verdicts | Tested |
| Reuse beyond original C fixture | Unmodified nginx backend and independent file observation | Demonstrated on Linux |
| Find an unseeded independent QNX bug | None | Open research goal |
| Outside developer reproduction | Automated clean-package checks only | Human trial still open |
| Entry materials | Public MIT source, build/run guide and native evidence | Video and Devpost receipt tracked in competition-entry.md |

The authored application policies are ours. No QNX or nginx vulnerability,
production safety property, motor efficiency improvement or worst-case latency
claim follows. Existing fault injection and delta debugging techniques are not
claimed as inventions. The contribution is a small effect-to-regression workflow
with native QNX observation, source-bound captures and a target without Python.

The remaining human trial and independent-application experiment would strengthen
the project. They are not formal entry requirements. A codelab is optional unless
entering the codelab bonus category.
