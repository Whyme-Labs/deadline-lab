/* Deliberately separate POSIX transport fixtures. They implement NO QNX API and
 * supply NO native cancellation evidence. They exercise process I/O and
 * cleanup.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
static volatile sig_atomic_t stop = 0;
static void request_stop(int n) {
  (void)n;
  stop = 1;
}
static uint64_t now(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t))
    _Exit(70);
  return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static void sleep_ms(long ms) {
  struct timespec t = {ms / 1000, ms % 1000 * 1000000};
  while (nanosleep(&t, &t) && errno == EINTR && !stop) {
  }
}
int main(int argc, char **argv) {
  const char *role = strrchr(argv[0], '-');
  if (!role)
    return 64;
  role++;
  if (!strcmp(role, "abi")) {
    puts("{\"schema\":1,\"system\":\"POSIX-TRANSPORT-TEST\",\"qnx_executed\":"
         "false}");
    return 0;
  }
  if (!strcmp(role, "client")) {
    if (argc != 7)
      return 64;
    /* Test-only selectors use WORK_MS, not native IPC or a shared clock model.
     */
    int work = atoi(argv[5]);
    if (work == 998) {
      for (;;)
        sleep_ms(100);
    }
    if (work == 997) {
      for (int i = 0; i < 70000; i++)
        fputc('c', stdout);
      fflush(stdout);
      return 0;
    }
    if (work == 996)
      return 19;
    printf("{\"kind\":\"transport-client\",\"id\":%s,\"pid\":%ld,\"qnx_"
           "executed\":false}\n",
           argv[4], (long)getpid());
    return 0;
  }
  if (strcmp(role, "server") || argc != 5)
    return 64;
  const char *mode = argv[1];
  FILE *log = fopen(argv[3], "wx");
  if (!log)
    return 73;
  fprintf(log, "{\"kind\":\"transport-start\",\"pid\":%ld}\n", (long)getpid());
  fflush(log);
  signal(SIGTERM, request_stop);
  signal(SIGINT, request_stop);
  signal(SIGPIPE, SIG_IGN);
  if (!strcmp(mode, "stubborn"))
    signal(SIGTERM, SIG_IGN);
  if (!strcmp(mode, "crash")) {
    fclose(log);
    return 23;
  }
  if (!strcmp(mode, "partial")) {
    printf("READY %ld", (long)getpid());
    fflush(stdout);
    while (!stop)
      sleep_ms(10);
    fclose(log);
    return 0;
  }
  if (!strcmp(mode, "wrong_pid")) {
    printf("READY %ld 0 1\n", (long)getpid() + 1);
    fflush(stdout);
  } else {
    printf("READY %ld 0 1\n", (long)getpid());
    fflush(stdout);
  }
  if (!strcmp(mode, "flood")) {
    for (int i = 0; i < 70000; i++) {
      fputc('x', stdout);
      fputc('y', stderr);
    }
    fflush(stdout);
    fflush(stderr);
  }
  if (!strcmp(mode, "stderr_burst")) {
    for (int i = 0; i < 48000; i++)
      fputc('e', stderr);
    fflush(stderr);
  }
  if (!strcmp(mode, "partial_effect")) {
    if (write(3, "E 1 1", 5) != 5)
      return 74;
  } else if (!strcmp(mode, "bad_effect")) {
    const char data[3] = {'E', 0, '\n'};
    if (write(3, data, 3) != 3)
      return 74;
  } else if (!strcmp(mode, "oversize_effect")) {
    char data[258];
    memset(data, 'E', sizeof(data));
    data[257] = '\n';
    if (write(3, data, sizeof(data)) != (ssize_t)sizeof(data))
      return 74;
  } else {
    unsigned n = !strcmp(mode, "many_effects") ? 129
                 : !strcmp(mode, "burst")      ? 100
                                               : 1;
    for (unsigned i = 0; i < n; i++) {
      char line[160];
      int len = snprintf(line, sizeof(line), "E %u 1 1 %u %" PRIu64 " 1\n",
                         i + 1, i + 1, now());
      if (write(3, line, (size_t)len) != len)
        break;
    }
  }
  while (!stop)
    sleep_ms(10);
  fprintf(log, "{\"kind\":\"transport-end\"}\n");
  fclose(log);
  close(3);
  return 0;
}
