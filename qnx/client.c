#ifndef __QNXNTO__
#error "This source requires the actual QNX SDK"
#endif
#define _QNX_SOURCE 1
#include "wire.h"
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/neutrino.h>
#include <time.h>
#include <unistd.h>

static uint64_t now_ns(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) exit(70);
    return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static int number(const char *s, uint64_t *value) {
    if (!*s || *s == '-' || *s == '+') return -1;
    errno = 0;
    char *end;
    *value = strtoull(s, &end, 10);
    return errno || *end ? -1 : 0;
}
int main(int argc, char **argv) {
    if (argc != 7) {
        fprintf(stderr, "usage: dl-qnx-client PID CHID EPOCH ID WORK_MS TIMEOUT_MS\n"); return 64;
    }
    uint64_t a[6];
    for (int i = 0; i < 6; ++i) if (number(argv[i + 1], &a[i])) return 64;
    if (!a[0] || a[0] > INT_MAX || a[1] > INT_MAX || !a[2] || !a[3] ||
        a[4] > 1000 || a[5] < 1 || a[5] > 5000) return 64;
    int coid = ConnectAttach(0, (pid_t)a[0], (int)a[1], _NTO_SIDE_CHANNEL, 0);
    if (coid == -1) { perror("ConnectAttach"); return 77; }
    dl_qnx_request request;
    memset(&request, 0, sizeof(request));
    request.magic = DL_QNX_MAGIC;
    request.version = DL_SCHEMA;
    request.work_ms = (uint32_t)a[4];
    request.command.id = a[3];
    request.command.epoch = a[2];
    request.command.issued_ns = now_ns();
    /* Transport timeout is intentionally distinct from authorisation expiry. */
    request.command.expires_ns = request.command.issued_ns + UINT64_C(10000000000);
    request.command.delta = 1;
    dl_qnx_reply reply = {0};
    uint64_t timeout_ns = a[5] * UINT64_C(1000000);
    uint64_t start = now_ns();
    if (TimerTimeout(CLOCK_MONOTONIC, _NTO_TIMEOUT_SEND | _NTO_TIMEOUT_REPLY,
                     NULL, &timeout_ns, NULL) == -1) { perror("TimerTimeout"); return 70; }
    int status = MsgSend(coid, &request, sizeof(request), &reply, sizeof(reply));
    int saved_errno = status == -1 ? errno : 0;
    uint64_t end = now_ns();
    (void)ConnectDetach(coid);
    printf("{\"id\":%" PRIu64 ",\"status\":%d,\"errno\":%d,\"reply_result\":%u,"
           "\"elapsed_ns\":%" PRIu64 "}\n", a[3], status, saved_errno, reply.result, end-start);
    /* Expected timeout is an observation, not an infrastructure exit failure. */
    return 0;
}
