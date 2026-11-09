# References checked during this scaffold

Primary QNX documentation was retrieved on 9 November 2026. These sources justify design choices; they do not establish that the uncompiled QNX adapter works.

- R1. QNX SDP 8.0, TimerTimeout. Documents timeout states, call placement and the `_NTO_CHF_UNBLOCK` exception.
  https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/t/timertimeout.html
- R2. QNX SDP 8.0, ChannelCreate. Documents unblock/disconnect semantics and public-channel ability requirements.
  https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/c/channelcreate.html
- R3. QNX SDP 8.0, Handling client unblocking due to signals or timeouts. Explains checking the current message information before acting on unblock notifications.
  https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.resmgr/topic/signals_HANDLING_UNBLOCKING.html
- R4. QNX SDP 8.0, MsgError. Restricts `error=-1` to unblock-pulse handling.
  https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/m/msgerror.html
- R5. QNX SDP 8.0, MsgReceive. Documents `rcvid_t`, pulse buffer requirements, message lengths and the rule against replying to a pulse.
  https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/m/msgreceive.html
- R6. QNX SDP 8.0, Using the `_NTO_MI_UNBLOCK_REQ` flag.
  https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.getting_started/topic/s1_msg_nto_mi_unblock_req.html
- R7. QNX SDP 8.0, MsgInfo and message information structure.
  https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/m/msginfo.html
  https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/m/_msg_info.html
- R8. QNX Global Hackathon rules. Search-index retrieval confirmed a Developer Tooling & Host Tools category and the requirement for meaningful QNX-oriented work. Direct page retrieval was intermittent in this session. Deadline and prize figures were not freshly re-certified and are intentionally not repeated as current facts in this scaffold report.
  https://qnx.devpost.com/rules

The prior 9 November research memo remains a separate user-provided artifact. It is not copied into this source tree because it includes internal project-status material irrelevant to a public example.

## v0.2.0 independent-target additions

- R9. nginx DAV module. Documents supported PUT operations and file management. Used for an independent local effect target; no nginx defect is alleged.
  https://nginx.org/en/docs/http/ngx_http_dav_module.html
- R10. nginx command-line parameters. Documents `-p` for a private prefix, `-c` for a private configuration and `-V` for build identification.
  https://nginx.org/en/docs/switches.html
- R11. nginx core directives. Documents foreground/developer process settings. The lab runs its own foreground process, not an existing service.
  https://nginx.org/en/docs/ngx_core_module.html

R1, R3 and R4 were rechecked while extending the native observer path. No new platform execution evidence follows from that documentation review. An attempted libmodbus source download could not complete in this environment; no libmodbus source or executable was used in the delivered experiment.


## v0.3.0 documentation recheck

R1, R2, R4 and R7 were reopened during this revision. Their documentation does not substitute for executing the native implementation.

- R12. QNX SDP 8.0, q++, qcc. Compiler invocation and target variant selection.
  https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/q/qcc.html

The late-unblock checker correction is our test-contract decision. The experiment must establish the intended pre-commit condition before claiming its cancellation policy failed. It is not a claim that every QNX service must cancel every operation, or that a timeout reverses an already committed effect.

## v0.4 portable target collector references

Reviewed 10 November 2026, UTC+8. These are API references, not evidence of a completed QNX build.

- QNX 8 posix_spawn: https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/p/posix_spawn.html
- QNX 8 poll: https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.lib_ref/topic/p/poll.html
- QNX 8 SSH utility: https://www.qnx.com/developers/docs/8.0/com.qnx.doc.neutrino.utilities/topic/s/ssh.html
