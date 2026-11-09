#define _POSIX_C_SOURCE 200809L
#include "dl_effect.h"
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <unistd.h>

int dl_emit_effect(int fd, const dl_command *e, uint64_t epoch,
                   uint64_t attempt, uint64_t commit_ns) {
    if (fd < 0 || e == NULL || !e->id || !e->epoch || !epoch || !attempt || !commit_ns ||
        e->delta == 0 || e->delta < -1000000 || e->delta > 1000000) {
        errno = EINVAL; return -1;
    }
    char line[256];
    int n = snprintf(line, sizeof(line), "E %" PRIu64 " %" PRIu64 " %" PRIu64
        " %" PRIu64 " %" PRIu64 " %" PRId32 "\n",
        e->id, e->epoch, epoch, attempt, commit_ns, e->delta);
    if (n < 0 || (size_t)n >= sizeof(line)) { errno = EOVERFLOW; return -1; }
    /* Smaller than POSIX's minimum PIPE_BUF. Never reuse for arbitrary network IO. */
    ssize_t wrote;
    do { wrote = write(fd, line, (size_t)n); } while (wrote < 0 && errno == EINTR);
    if (wrote != n) { if (wrote >= 0) errno = EIO; return -1; }
    return 0;
}
