/* Native ABI/runtime record. Never compiled with invented QNX headers. */
#ifndef __QNXNTO__
#error "Actual QNX SDK required"
#endif
#define _QNX_SOURCE 1
#include "wire.h"
#include <stdio.h>
#include <sys/neutrino.h>
#include <sys/utsname.h>

static void json_string(const char *s) {
    putchar('"');
    for (; *s; ++s) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') { putchar('\\'); putchar(c); }
        else if (c < 32 || c > 126) printf("\\u%04x", (unsigned int)c);
        else putchar(c);
    }
    putchar('"');
}

int main(void) {
    struct utsname u;
    if (uname(&u) != 0) return 70;
    printf("{\"schema\":1,\"system\":"); json_string(u.sysname);
    printf(",\"release\":"); json_string(u.release);
    printf(",\"machine\":"); json_string(u.machine);
    printf(",\"rcvid_bytes\":%zu,\"request_bytes\":%zu,\"reply_bytes\":%zu,"
           "\"dl_schema\":%u}\n", sizeof(rcvid_t), sizeof(dl_qnx_request),
           sizeof(dl_qnx_reply), (unsigned int)DL_SCHEMA);
    return ferror(stdout) ? 74 : 0;
}
