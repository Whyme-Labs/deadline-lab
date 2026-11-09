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
