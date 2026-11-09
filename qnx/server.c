/* QNX 8 native cancellation canary. NOT compiled or executed in the Linux evidence.
 * Only simulated effects; never attach this fixture to a physical motor.
 * See docs/qnx-native-gate.md and docs/references.md for the documented semantics.
 */
#ifndef __QNXNTO__
#error "This source requires the actual QNX SDK; no mock kernel backend is provided"
#endif
#define _QNX_SOURCE 1
#include "wire.h"
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/neutrino.h>
#include <time.h>
#include <unistd.h>

static uint64_t now_ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) { perror("clock_gettime"); exit(70); }
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}

static void event(FILE *log, const char *kind, uint64_t id, uint64_t stamp, int detail) {
    if (fprintf(log, "{\"kind\":\"%s\",\"id\":%" PRIu64 ",\"monotonic_ns\":%" PRIu64
                ",\"detail\":%d}\n", kind, id, stamp, detail) < 0 || fflush(log) != 0) {
        perror("event log"); exit(74);
    }
}

int main(int argc, char **argv) {
    if (argc != 4 || (strcmp(argv[1], "reference") && strcmp(argv[1], "ignore_unblock"))) {
        fprintf(stderr, "usage: dl-qnx-server reference|ignore_unblock EPOCH LOGFILE\n"); return 64;
    }
    char *end = NULL;
    errno = 0;
    uint64_t epoch = strtoull(argv[2], &end, 10);
    if (errno || !epoch || *end || argv[2][0] == '-') return 64;
    bool ignore_unblock = strcmp(argv[1], "ignore_unblock") == 0;
    FILE *log = fopen(argv[3], "wx");
    if (!log) { perror("log creation"); return 73; }
    int chid = ChannelCreate(_NTO_CHF_UNBLOCK | _NTO_CHF_DISCONNECT);
    if (chid == -1) { perror("ChannelCreate; check target public-channel ability"); fclose(log); return 77; }
    dl_state state;
    dl_init(&state, epoch, 0);
    rcvid_t pending = 0;
    dl_command active = {0};
    uint64_t due = 0, started = now_ns();
    printf("READY %ld %d %" PRIu64 "\n", (long)getpid(), chid, epoch);
    fflush(stdout);
    event(log, "start", 0, started, ignore_unblock);
    while (now_ns() - started < UINT64_C(30000000000)) {
        if (pending > 0 && now_ns() >= due) {
            struct _msg_info info;
            if (MsgInfo(pending, &info) == -1) {
                /* Client disappeared; never turn unknown ownership into an effect. */
                event(log, "client_gone", active.id, now_ns(), errno);
                dl_abandon(&state); pending = 0; continue;
            }
            if (!ignore_unblock && (info.flags & _NTO_MI_UNBLOCK_REQ)) {
                (void)dl_cancel(&state, active.id);
                /* This is a pre-commit check, not processing the pulse itself.
                 * Use explicit ECANCELED, never MsgError(...,-1) here. */
                if (MsgError(pending, ECANCELED) == -1 && errno != ESRCH) {
                    perror("MsgError"); break;
                }
                event(log, "cancel_precommit", active.id, now_ns(), ECANCELED);
                dl_abandon(&state); pending = 0; continue;
            }
            dl_command effect;
            uint64_t stamp = now_ns();
            dl_result r = dl_commit(&state, active.id, stamp, &effect);
            if (r == DL_APPLY) event(log, "effect", effect.id, stamp, effect.delta);
            else event(log, "reject", active.id, stamp, (int)r);
            dl_qnx_reply reply = {DL_SCHEMA, (uint32_t)r, active.id};
            if (MsgReply(pending, 0, &reply, sizeof(reply)) == -1 && errno != ESRCH) {
                perror("MsgReply"); break;
            }
            pending = 0;
            continue;
        }
        union { struct _pulse pulse; dl_qnx_request request; } message;
        struct _msg_info info;
        memset(&message, 0, sizeof(message));
        uint64_t wait_ns = UINT64_C(100000000);
        if (pending > 0) {
            uint64_t now = now_ns();
            wait_ns = due > now ? due - now : 1;
            if (wait_ns > UINT64_C(100000000)) wait_ns = UINT64_C(100000000);
        }
        if (TimerTimeout(CLOCK_MONOTONIC, _NTO_TIMEOUT_RECEIVE, NULL, &wait_ns, NULL) == -1) {
            perror("TimerTimeout"); break;
        }
        rcvid_t rcvid = MsgReceive(chid, &message, sizeof(message), &info);
        if (rcvid == -1) {
            if (errno == ETIMEDOUT || errno == EINTR) continue;
            perror("MsgReceive"); break;
        }
        if (rcvid == 0) {
            if (message.pulse.code == _PULSE_CODE_DISCONNECT) {
                /* Mandatory release of the server-side connection identifier. */
                if (ConnectDetach(message.pulse.scoid) == -1 && errno != ESRCH) {
                    perror("ConnectDetach"); break;
                }
            } else if (message.pulse.code == _PULSE_CODE_UNBLOCK && pending > 0) {
                /* One pending request only. Query its current kernel flag rather
                 * than blindly trusting a pulse rcvid or truncating rcvid_t. */
                struct _msg_info current;
                if (MsgInfo(pending, &current) != -1 && (current.flags & _NTO_MI_UNBLOCK_REQ)) {
                    event(log, "unblock_observed", active.id, now_ns(), ignore_unblock);
                    if (!ignore_unblock) {
                        (void)dl_cancel(&state, active.id);
                        /* -1 is defined here because this handles an unblock pulse. */
                        if (MsgError(pending, -1) == -1 && errno != ESRCH) {
                            perror("MsgError"); break;
                        }
                        event(log, "cancel_ack", active.id, now_ns(), 0);
                        dl_abandon(&state); pending = 0;
                    }
                }
            }
            continue; /* A pulse itself never receives MsgReply. */
        }
        if ((size_t)info.msglen != sizeof(dl_qnx_request) ||
            (size_t)info.srcmsglen != sizeof(dl_qnx_request) ||
            message.request.magic != DL_QNX_MAGIC || message.request.version != DL_SCHEMA ||
            message.request.reserved != 0 || message.request.work_ms > 1000) {
            (void)MsgError(rcvid, EINVAL); continue;
        }
        if (pending > 0) { (void)MsgError(rcvid, EBUSY); continue; }
        dl_result r = dl_prepare(&state, &message.request.command);
        if (r != DL_OK) { (void)MsgError(rcvid, EINVAL); continue; }
        pending = rcvid;
        active = message.request.command;
        due = now_ns() + (uint64_t)message.request.work_ms * UINT64_C(1000000);
        event(log, "received", active.id, now_ns(), (int)message.request.work_ms);
    }
    if (pending > 0) (void)MsgError(pending, ECANCELED);
    event(log, "end", 0, now_ns(), 0);
    (void)ChannelDestroy(chid);
    fclose(log);
    return 0;
}
