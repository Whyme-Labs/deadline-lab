#define _POSIX_C_SOURCE 200809L
#include "dl_effect.h"
#include <assert.h>
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(void) {
    signal(SIGPIPE, SIG_IGN);
    dl_command command = {1, 2, 1, 999, -7};
    int fds[2];
    assert(pipe(fds) == 0);
    assert(dl_emit_effect(fds[1], &command, 3, 4, 5) == 0);
    char data[256] = {0};
    assert(read(fds[0], data, sizeof(data)) == 15);
    assert(strcmp(data, "E 1 2 3 4 5 -7\n") == 0);
    assert(dl_emit_effect(-1, &command, 3, 4, 5) == -1 && errno == EINVAL);
    assert(dl_emit_effect(fds[1], NULL, 3, 4, 5) == -1 && errno == EINVAL);
    assert(dl_emit_effect(fds[1], &command, 0, 4, 5) == -1 && errno == EINVAL);
    command.delta = 0;
    assert(dl_emit_effect(fds[1], &command, 3, 4, 5) == -1 && errno == EINVAL);
    command.delta = 1;
    close(fds[0]);
    assert(dl_emit_effect(fds[1], &command, 3, 4, 5) == -1 && errno == EPIPE);
    close(fds[1]);
    puts("9 effect-sink assertions passed");
    return 0;
}
