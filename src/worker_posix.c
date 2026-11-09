#define _POSIX_C_SOURCE 200809L
#include "dl_core.h"
#include "dl_effect.h"
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static uint64_t monotonic_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) { perror("clock_gettime"); exit(70); }
    return (uint64_t)ts.tv_sec * UINT64_C(1000000000) + (uint64_t)ts.tv_nsec;
}

static int parse_u64(const char *s, uint64_t *value) {
    if (!s || !*s || *s == '-' || *s == '+') return -1;
    char *end = NULL;
    errno = 0;
    unsigned long long v = strtoull(s, &end, 10);
    if (errno || *end) return -1;
    *value = (uint64_t)v;
    return 0;
}

static int parse_delta(const char *s, int32_t *value) {
    if (!s || !*s) return -1;
    errno = 0;
    char *end = NULL;
    long v = strtol(s, &end, 10);
    if (errno || *end || v < -1000000 || v > 1000000 || v == 0) return -1;
    *value = (int32_t)v;
    return 0;
}


int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: dl-worker MODE EPOCH EFFECT_FD\n"); return 64;
    }
    unsigned mode;
    uint64_t epoch, raw_fd;
    if (dl_parse_mode(argv[1], &mode) || parse_u64(argv[2], &epoch) || !epoch ||
        parse_u64(argv[3], &raw_fd) || raw_fd > INT_MAX) return 64;
    int effect_fd = (int)raw_fd;
    signal(SIGPIPE, SIG_IGN);
    setvbuf(stdout, NULL, _IOLBF, 0);
    dl_state state;
    dl_init(&state, epoch, mode);
    printf("READY %" PRIu64 " %ld\n", epoch, (long)getpid());
    char line[512];
    while (fgets(line, sizeof(line), stdin)) {
        if (!strchr(line, '\n')) {
            int ch;
            while ((ch = getchar()) != '\n' && ch != EOF) {}
            puts("R invalid"); continue;
        }
        char *tokens[9], *save = NULL;
        size_t count = 0;
        for (char *t = strtok_r(line, " \t\r\n", &save); t && count < 9;
             t = strtok_r(NULL, " \t\r\n", &save)) tokens[count++] = t;
        if (count == 0) { puts("R invalid"); continue; }
        dl_result result = DL_INVALID;
        if (count == 6 && strcmp(tokens[0], "P") == 0) {
            dl_command c;
            if (!parse_u64(tokens[1], &c.id) && !parse_u64(tokens[2], &c.epoch) &&
                !parse_u64(tokens[3], &c.issued_ns) && !parse_u64(tokens[4], &c.expires_ns) &&
                !parse_delta(tokens[5], &c.delta)) result = dl_prepare(&state, &c);
        } else if (count == 2 && strcmp(tokens[0], "X") == 0) {
            uint64_t id;
            if (!parse_u64(tokens[1], &id)) result = dl_cancel(&state, id);
        } else if (count == 3 && (strcmp(tokens[0], "C") == 0 || strcmp(tokens[0], "L") == 0)) {
            uint64_t id, attempt;
            if (!parse_u64(tokens[1], &id) && !parse_u64(tokens[2], &attempt)) {
                dl_command effect;
                uint64_t commit_ns = monotonic_ns();
                result = dl_commit(&state, id, commit_ns, &effect);
                if (result == DL_APPLY && dl_emit_effect(effect_fd, &effect, epoch, attempt, commit_ns)) {
                    perror("effect pipe"); return 74;
                }
                /* L is an explicit test hook: suppress the acknowledgement. */
                if (strcmp(tokens[0], "L") == 0) continue;
            }
        } else if (count == 1 && strcmp(tokens[0], "A") == 0) {
            dl_abandon(&state); result = DL_OK;
        } else if (count == 1 && strcmp(tokens[0], "H") == 0) {
            result = DL_OK;
        } else if (count == 1 && strcmp(tokens[0], "Q") == 0) {
            puts("R ok"); return 0;
        }
        printf("R %s\n", dl_result_name(result));
    }
    return ferror(stdin) ? 74 : 0;
}
