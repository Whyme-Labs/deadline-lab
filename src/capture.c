/* Target-side capture with no Python, shell execution, SDK or network
 * dependency. Portable supervision runs on Linux; actual QNX IPC lives only in
 * the qnx directory.
 * --transport-fixture selects explicitly non-native process-I/O test binaries.
 * Never connect this collector's demonstration to physical machinery.
 */
#define _POSIX_C_SOURCE 200809L
#define _XOPEN_SOURCE 700
#include "dl_sha256.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <poll.h>
#include <signal.h>
#include <spawn.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
extern char **environ;
#define LIMIT 65536
#define MAX_CALLS 9
#define MAX_FILES 40
#define PATH_LEN 4096

typedef struct {
  int fd;
  size_t used;
  char data[LIMIT + 1];
} stream;
typedef struct {
  pid_t pid;
  bool reaped;
  int status;
  stream out, err;
} child;
typedef struct {
  unsigned work, timeout;
} call;
typedef struct {
  child server, current;
  int effect_fd;
  char effect_line[257];
  size_t effect_used;
  FILE *effects;
  size_t effect_count;
  bool effect_eof;
  uint64_t deadline;
  const char *error;
  int server_exit, observer_exit;
} context;
static volatile sig_atomic_t interrupted = 0;
static void stop_signal(int n) { interrupted = n; }
static uint64_t now_ns(void) {
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t))
    _Exit(70);
  return (uint64_t)t.tv_sec * UINT64_C(1000000000) + (uint64_t)t.tv_nsec;
}
static int ns_wait(uint64_t deadline) {
  uint64_t now = now_ns();
  if (now >= deadline)
    return 0;
  uint64_t ms = (deadline - now + 999999) / 1000000;
  return ms > 20 ? 20 : (int)ms;
}
static void init_child(child *c) {
  memset(c, 0, sizeof(*c));
  c->out.fd = c->err.fd = -1;
  c->status = -999;
}
static void json_string(FILE *f, const char *s) {
  fputc('"', f);
  for (; *s; s++) {
    unsigned char c = (unsigned char)*s;
    if (c == '"' || c == '\\') {
      fputc('\\', f);
      fputc(c, f);
    } else if (c < 32 || c > 126)
      fprintf(f, "\\u%04x", (unsigned)c);
    else
      fputc(c, f);
  }
  fputc('"', f);
}
static int path_join(char *dst, const char *dir, const char *name) {
  int n = snprintf(dst, PATH_LEN, "%s/%s", dir, name);
  return n < 0 || n >= PATH_LEN ? -1 : 0;
}
static FILE *new_file(const char *dir, const char *name) {
  char p[PATH_LEN];
  if (path_join(p, dir, name))
    return NULL;
  int fd = open(p, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
  if (fd < 0)
    return NULL;
  FILE *f = fdopen(fd, "wb");
  if (!f)
    close(fd);
  return f;
}
static int bytes_file(const char *dir, const char *name, const char *buf,
                      size_t size) {
  FILE *f = new_file(dir, name);
  if (!f)
    return -1;
  int r = fwrite(buf, 1, size, f) == size ? 0 : -1;
  if (fclose(f))
    r = -1;
  return r;
}
static int high_fd(int fd) {
  int n = fcntl(fd, F_DUPFD_CLOEXEC, 64);
  int e = errno;
  close(fd);
  errno = e;
  return n;
}
static int pipe_pair(int p[2]) {
  int raw[2];
  if (pipe(raw))
    return -1;
  p[0] = high_fd(raw[0]);
  p[1] = high_fd(raw[1]);
  if (p[0] < 0 || p[1] < 0) {
    if (p[0] >= 0)
      close(p[0]);
    if (p[1] >= 0)
      close(p[1]);
    p[0] = p[1] = -1;
    return -1;
  }
  return 0;
}
static void close_stream(stream *s) {
  if (s->fd >= 0)
    close(s->fd);
  s->fd = -1;
}
static int nonblock(int fd) {
  int flags = fcntl(fd, F_GETFL);
  return flags < 0 ? -1 : fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}
static int spawn_child(child *c, char *const argv[], int effect_fd) {
  int op[2] = {-1, -1}, ep[2] = {-1, -1}, rc = 0;
  bool fi = false, ai = false;
  posix_spawn_file_actions_t fa;
  posix_spawnattr_t at;
  init_child(c);
  if (pipe_pair(op) || pipe_pair(ep))
    goto io_error;
  if ((rc = posix_spawn_file_actions_init(&fa)))
    goto done;
  fi = true;
  if ((rc = posix_spawnattr_init(&at)))
    goto done;
  ai = true;
#define ACT(x)                                                                 \
  do {                                                                         \
    rc = (x);                                                                  \
    if (rc)                                                                    \
      goto done;                                                               \
  } while (0)
  ACT(posix_spawn_file_actions_addopen(&fa, 0, "/dev/null", O_RDONLY, 0));
  ACT(posix_spawn_file_actions_adddup2(&fa, op[1], 1));
  ACT(posix_spawn_file_actions_adddup2(&fa, ep[1], 2));
  if (effect_fd >= 0)
    ACT(posix_spawn_file_actions_adddup2(&fa, effect_fd, 3));
  sigset_t empty, defaults;
  sigemptyset(&empty);
  sigemptyset(&defaults);
  sigaddset(&defaults, SIGINT);
  sigaddset(&defaults, SIGTERM);
  sigaddset(&defaults, SIGPIPE);
  ACT(posix_spawnattr_setsigmask(&at, &empty));
  ACT(posix_spawnattr_setsigdefault(&at, &defaults));
  ACT(posix_spawnattr_setpgroup(&at, 0));
  ACT(posix_spawnattr_setflags(&at, POSIX_SPAWN_SETSIGMASK |
                                        POSIX_SPAWN_SETSIGDEF |
                                        POSIX_SPAWN_SETPGROUP));
  ACT(posix_spawn(&c->pid, argv[0], &fa, &at, argv, environ));
#undef ACT
  c->out.fd = op[0];
  op[0] = -1;
  c->err.fd = ep[0];
  ep[0] = -1;
  if (nonblock(c->out.fd) || nonblock(c->err.fd)) {
    rc = errno;
    goto done;
  }
done:
  if (fi)
    posix_spawn_file_actions_destroy(&fa);
  if (ai)
    posix_spawnattr_destroy(&at);
  for (int i = 0; i < 2; i++) {
    if (op[i] >= 0)
      close(op[i]);
    if (ep[i] >= 0)
      close(ep[i]);
  }
  if (rc) {
    errno = rc;
    return -1;
  }
  return 0;
io_error:
  rc = errno;
  goto done;
}
static void reap(child *c) {
  if (c->pid <= 0 || c->reaped)
    return;
  int status;
  pid_t r = waitpid(c->pid, &status, WNOHANG);
  if (r == c->pid) {
    c->reaped = true;
    c->status = WIFEXITED(status)     ? WEXITSTATUS(status)
                : WIFSIGNALED(status) ? -WTERMSIG(status)
                                      : -998;
  } else if (r < 0 && errno != EINTR) {
    c->reaped = true;
    c->status = -997;
  }
}
static int drain_stream(stream *s) {
  if (s->fd < 0)
    return 0;
  char buf[4096];
  /* A finite read quota also bounds a continuously writing child. */
  for (unsigned k = 0; k < 16; k++) {
    ssize_t n = read(s->fd, buf, sizeof(buf));
    if (n == 0) {
      close_stream(s);
      return 0;
    }
    if (n < 0) {
      if (errno == EINTR)
        continue;
      if (errno == EAGAIN || errno == EWOULDBLOCK)
        return 0;
      return -1;
    }
    if (s->used + (size_t)n > LIMIT) {
      errno = EFBIG;
      return -1;
    }
    memcpy(s->data + s->used, buf, (size_t)n);
    s->used += (size_t)n;
    s->data[s->used] = 0;
  }
  return 0;
}
static int drain_effects(context *c) {
  if (c->effect_fd < 0)
    return 0;
  char buf[1024];
  for (unsigned j = 0; j < 16; j++) {
    ssize_t n = read(c->effect_fd, buf, sizeof(buf));
    if (n == 0) {
      close(c->effect_fd);
      c->effect_fd = -1;
      c->effect_eof = true;
      return c->effect_used ? -1 : 0;
    }
    if (n < 0) {
      if (errno == EINTR)
        continue;
      if (errno == EAGAIN || errno == EWOULDBLOCK)
        return 0;
      return -1;
    }
    for (ssize_t k = 0; k < n; k++) {
      unsigned char b = (unsigned char)buf[k];
      if (c->effect_used >= 256 || (b != 10 && (b < 32 || b > 126)))
        return -1;
      c->effect_line[c->effect_used++] = (char)b;
      if (b == 10) {
        c->effect_line[c->effect_used] = 0;
        if (++c->effect_count > 128)
          return -1;
        fprintf(c->effects,
                "{\"kind\":\"effect\",\"observed_ns\":%" PRIu64 ",\"wire\":",
                now_ns());
        json_string(c->effects, c->effect_line);
        fputs("}\n", c->effects);
        if (fflush(c->effects))
          return -1;
        c->effect_used = 0;
      }
    }
  }
  return 0;
}
static int pump(context *c, uint64_t deadline, bool cleanup) {
  if (!cleanup && interrupted) {
    c->error = "interrupted";
    return -1;
  }
  if (now_ns() >= deadline) {
    if (!cleanup)
      c->error = "operation deadline expired";
    return -1;
  }
  struct pollfd p[5];
  int n = 0;
  int fd[5] = {c->server.out.fd, c->server.err.fd, c->current.out.fd,
               c->current.err.fd, c->effect_fd};
  for (int i = 0; i < 5; i++)
    if (fd[i] >= 0)
      p[n++] = (struct pollfd){fd[i], POLLIN, 0};
  int r = poll(p, (nfds_t)n, ns_wait(deadline));
  if (r < 0 && errno != EINTR) {
    c->error = "poll failed";
    return -1;
  }
  if (drain_stream(&c->server.out) || drain_stream(&c->server.err) ||
      drain_stream(&c->current.out) || drain_stream(&c->current.err)) {
    c->error = "child output exceeded bound or read failed";
    return -1;
  }
  if (drain_effects(c)) {
    c->error = "invalid, oversized or incomplete effect stream";
    return -1;
  }
  reap(&c->server);
  reap(&c->current);
  return 0;
}
static uint64_t bounded_deadline(context *c, unsigned milliseconds) {
  uint64_t d = now_ns() + (uint64_t)milliseconds * 1000000;
  return d < c->deadline ? d : c->deadline;
}
static bool finished(const child *c) {
  return c->reaped && c->out.fd < 0 && c->err.fd < 0;
}
static int wait_current(context *c, unsigned ms) {
  uint64_t d = bounded_deadline(c, ms);
  while (!finished(&c->current)) {
    if (pump(c, d, false))
      return -1;
  }
  if (c->current.status != 0) {
    c->error = "child exited unsuccessfully";
    return -1;
  }
  return 0;
}
static void terminate_child(child *c) {
  reap(c);
  if (c->pid <= 0 || c->reaped)
    return;
  (void)kill(c->pid, SIGTERM);
  uint64_t d = now_ns() + UINT64_C(200000000);
  while (!c->reaped && now_ns() < d) {
    reap(c);
    struct timespec t = {0, 1000000};
    (void)nanosleep(&t, NULL);
  }
  if (!c->reaped) {
    (void)kill(c->pid, SIGKILL);
    d = now_ns() + UINT64_C(1000000000);
    while (!c->reaped && now_ns() < d) {
      reap(c);
      struct timespec t = {0, 1000000};
      (void)nanosleep(&t, NULL);
    }
  }
}
static int save_child(const char *dir, const char *role, const child *c) {
  char name[64];
  snprintf(name, sizeof(name), "%s.stdout", role);
  if (bytes_file(dir, name, c->out.data, c->out.used))
    return -1;
  snprintf(name, sizeof(name), "%s.stderr", role);
  return bytes_file(dir, name, c->err.data, c->err.used);
}
static int copy_small(const char *src, const char *dir, const char *name) {
  int fd = open(src, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0)
    return -1;
  struct stat st;
  if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size < 0 ||
      st.st_size > LIMIT) {
    close(fd);
    return -1;
  }
  char buf[LIMIT];
  size_t n = 0;
  for (;;) {
    ssize_t got = read(fd, buf + n, sizeof(buf) - n);
    if (got < 0 && errno == EINTR)
      continue;
    if (got < 0) {
      close(fd);
      return -1;
    }
    if (got == 0)
      break;
    n += (size_t)got;
    if (n == sizeof(buf))
      break;
  }
  close(fd);
  if (n != (size_t)st.st_size)
    return -1;
  return bytes_file(dir, name, buf, n);
}
static int unsigned_value(const char *s, unsigned max, unsigned *out) {
  if (!*s)
    return -1;
  unsigned v = 0;
  for (; *s; s++) {
    if (*s < '0' || *s > '9')
      return -1;
    if (v > (max - (unsigned)(*s - '0')) / 10)
      return -1;
    v = v * 10 + (unsigned)(*s - '0');
  }
  if (v > max)
    return -1;
  *out = v;
  return 0;
}
static int parse_calls(const char *s, call calls[MAX_CALLS], size_t *count) {
  if (strlen(s) > 255)
    return -1;
  char tmp[256];
  strcpy(tmp, s);
  char *save = NULL;
  *count = 0;
  if (!*s || s[0] == ',' || s[strlen(s) - 1] == ',' || strstr(s, ",,"))
    return -1;
  for (char *v = strtok_r(tmp, ",", &save); v; v = strtok_r(NULL, ",", &save)) {
    if (*count >= 8)
      return -1;
    char *sep = strchr(v, ':');
    if (!sep)
      return -1;
    *sep++ = 0;
    if (unsigned_value(v, 1000, &calls[*count].work) ||
        unsigned_value(sep, 5000, &calls[*count].timeout) ||
        !calls[*count].timeout)
      return -1;
    (*count)++;
  }
  calls[(*count)++] = (call){1, 1500};
  return 0;
}
static int write_all_deadline(int fd, const void *buffer, size_t size,
                              uint64_t deadline) {
  const char *p = buffer;
  while (size) {
    if (interrupted || now_ns() >= deadline)
      return -1;
    ssize_t n = write(fd, p, size);
    if (n > 0) {
      p += n;
      size -= (size_t)n;
      continue;
    }
    if (n < 0 && errno == EINTR)
      continue;
    if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
      struct pollfd f = {fd, POLLOUT, 0};
      (void)poll(&f, 1, ns_wait(deadline));
      continue;
    }
    return -1;
  }
  return 0;
}
static int stream_bundle(const char *dir, char files[MAX_FILES][64],
                         size_t count) {
  if (nonblock(STDOUT_FILENO))
    return -1;
  uint64_t deadline = now_ns() + UINT64_C(10000000000);
  if (write_all_deadline(1, "DLCAP1\n", 7, deadline))
    return -1;
  for (size_t i = 0; i < count; i++) {
    char path[PATH_LEN];
    if (path_join(path, dir, files[i]))
      return -1;
    int fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0)
      return -1;
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size < 0 ||
        st.st_size > LIMIT) {
      close(fd);
      return -1;
    }
    char header[128];
    int n = snprintf(header, sizeof(header), "FILE %s %ld\n", files[i],
                     (long)st.st_size);
    if (n < 0 || n >= (int)sizeof(header) ||
        write_all_deadline(1, header, (size_t)n, deadline)) {
      close(fd);
      return -1;
    }
    off_t left = st.st_size;
    char buf[4096];
    while (left) {
      size_t want = left > (off_t)sizeof(buf) ? sizeof(buf) : (size_t)left;
      ssize_t got = read(fd, buf, want);
      if (got < 0 && errno == EINTR)
        continue;
      if (got <= 0 || write_all_deadline(1, buf, (size_t)got, deadline)) {
        close(fd);
        return -1;
      }
      left -= got;
    }
    close(fd);
    if (write_all_deadline(1, "\n", 1, deadline))
      return -1;
  }
  return write_all_deadline(1, "END\n", 4, deadline);
}
static void add_file(char files[MAX_FILES][64], size_t *count,
                     const char *name) {
  if (*count >= MAX_FILES || strlen(name) > 63)
    _Exit(70);
  strcpy(files[(*count)++], name);
}

int main(int argc, char **argv) {
  const char *bin = NULL, *out_arg = NULL, *mode = NULL, *spec = NULL,
             *token = NULL;
  bool fixture = false, streaming = false;
  unsigned budget = 60000;
  for (int i = 1; i < argc; i++) {
    if (!strcmp(argv[i], "--transport-fixture")) {
      fixture = true;
      continue;
    }
    if (!strcmp(argv[i], "--stream")) {
      streaming = true;
      continue;
    }
    if (i + 1 >= argc)
      return 64;
    if (!strcmp(argv[i], "--bin"))
      bin = argv[++i];
    else if (!strcmp(argv[i], "--out"))
      out_arg = argv[++i];
    else if (!strcmp(argv[i], "--mode"))
      mode = argv[++i];
    else if (!strcmp(argv[i], "--calls"))
      spec = argv[++i];
    else if (!strcmp(argv[i], "--token"))
      token = argv[++i];
    else if (!strcmp(argv[i], "--budget-ms")) {
      if (unsigned_value(argv[++i], 60000, &budget) || budget < 200)
        return 64;
    } else
      return 64;
  }
  call calls[MAX_CALLS];
  size_t ncall = 0;
  if (!bin || bin[0] != '/' || !mode ||
      (!fixture && strcmp(mode, "reference") &&
       strcmp(mode, "ignore_unblock")) ||
      !spec || parse_calls(spec, calls, &ncall) || !token ||
      strlen(token) != 32 || strspn(token, "0123456789abcdef") != 32 ||
      streaming == (out_arg != NULL)) {
    fprintf(
        stderr,
        "usage: dl-capture --bin ABS --mode POLICY --calls WORK:TIMEOUT[,..] "
        "--token HEX32 (--stream | --out NEWDIR) [--transport-fixture]\n");
    return 64;
  }
  if (fixture && (!*mode || strlen(mode) > 40 ||
                  strspn(mode, "abcdefghijklmnopqrstuvwxyz_") != strlen(mode)))
    return 64;
  struct sigaction sa;
  memset(&sa, 0, sizeof(sa));
  sa.sa_handler = stop_signal;
  sigemptyset(&sa.sa_mask);
  sigaction(SIGINT, &sa, NULL);
  sigaction(SIGTERM, &sa, NULL);
  signal(SIGPIPE, SIG_IGN);
  /* Fail closed on missing standard streams: file-action mappings assume 0..2
   * exist. */
  for (int i = 0; i < 3; i++)
    if (fcntl(i, F_GETFD) < 0)
      return 74;
  char dir[PATH_LEN], path[PATH_LEN];
  bool temporary = false;
  if (streaming) {
    const char *tmp = getenv("TMPDIR");
    if (!tmp)
      tmp = "/tmp";
    if (path_join(dir, tmp, "deadline-capture-XXXXXX") || !mkdtemp(dir))
      return 73;
    temporary = true;
  } else {
    if (strlen(out_arg) >= PATH_LEN || mkdir(out_arg, 0700) ||
        !realpath(out_arg, dir))
      return 73;
  }
  char files[MAX_FILES][64];
  size_t file_count = 0;
  context *c = calloc(1, sizeof(*c));
  if (!c)
    return 71;
  init_child(&c->server);
  init_child(&c->current);
  c->effect_fd = -1;
  c->server_exit = -999;
  c->observer_exit = -999;
  c->deadline = now_ns() + (uint64_t)budget * 1000000;
  struct utsname u;
  memset(&u, 0, sizeof(u));
  if (uname(&u)) {
    free(c);
    return 70;
  }
  bool native = false;
#ifdef __QNXNTO__
  native = !fixture && !strcmp(u.sysname, "QNX");
#endif
  const char *status = "INCOMPLETE";
  const char *origin = fixture ? "posix-capture-test" : "native-qnx";
  int code = 78;
  char binaries[4][PATH_LEN], before[4][65], after[4][65];
  size_t sizes[4] = {0};
  bool hashed = false;
  int exits[MAX_CALLS];
  pid_t pids[MAX_CALLS];
  size_t attempted = 0;
  memset(exits, 0, sizeof(exits));
  memset(pids, 0, sizeof(pids));
  const char *suffix[4] = {"server", "client", "abi", "capture"};
  char name[80];
  if (!fixture && !native) {
    origin = "unsupported-host";
    status = "NOT_RUN";
    c->error = "requires actual QNX compilation and runtime";
    code = 77;
    goto report;
  }
  for (int i = 0; i < 4; i++) {
    if (i == 3)
      snprintf(name, sizeof(name), "dl-capture");
    else
      snprintf(name, sizeof(name), "dl-%s-%s", fixture ? "transport" : "qnx",
               suffix[i]);
    if (path_join(binaries[i], bin, name) ||
        dl_sha256_file(binaries[i], before[i], &sizes[i])) {
      c->error = "missing or unhashable binary";
      goto report;
    }
  }
  hashed = true;
  if (!fixture) {
    const char *provenance[2] = {"build-record.json", "source-manifest.json"};
    for (int i = 0; i < 2; i++) {
      if (path_join(path, bin, provenance[i]) ||
          copy_small(path, dir, provenance[i])) {
        c->error = "native build provenance unavailable";
        goto finish;
      }
      add_file(files, &file_count, provenance[i]);
    }
  }
  {
    char *args[] = {binaries[2], NULL};
    if (spawn_child(&c->current, args, -1) || wait_current(c, 3000)) {
      if (!c->error)
        c->error = "ABI launch failed";
      goto finish;
    }
    if (save_child(dir, "abi", &c->current)) {
      c->error = "cannot save ABI observation";
      goto finish;
    }
    add_file(files, &file_count, "abi.stdout");
    add_file(files, &file_count, "abi.stderr");
    init_child(&c->current);
  }
  c->effects = new_file(dir, "effects.raw.jsonl");
  if (!c->effects) {
    c->error = "cannot create effect observation";
    goto finish;
  }
  add_file(files, &file_count, "effects.raw.jsonl");
  fprintf(c->effects,
          "{\"kind\":\"start\",\"monotonic_ns\":%" PRIu64 ",\"pid\":%ld}\n",
          now_ns(), (long)getpid());
  fflush(c->effects);
  {
    int p[2];
    if (pipe_pair(p)) {
      c->error = "effect pipe creation failed";
      goto finish;
    }
    c->effect_fd = p[0];
    if (nonblock(p[0])) {
      close(p[1]);
      c->error = "effect pipe flags failed";
      goto finish;
    }
    if (path_join(path, dir, "server.jsonl")) {
      close(p[1]);
      c->error = "path too long";
      goto finish;
    }
    char *args[] = {binaries[0], (char *)mode, "1", path, "3", NULL};
    int rc = spawn_child(&c->server, args, p[1]);
    close(p[1]);
    if (rc) {
      c->error = "server launch failed";
      goto finish;
    }
  }
  {
    uint64_t d = bounded_deadline(c, 3000);
    while (!memchr(c->server.out.data, '\n', c->server.out.used)) {
      if (pump(c, d, false))
        goto finish;
      if (c->server.reaped) {
        c->error = "server exited before greeting";
        goto finish;
      }
    }
  }
  long server_pid;
  int chid;
  uint64_t epoch = 1;
  int consumed = 0;
  char ptext[32], ctext[32], etext[32];
  unsigned pv = 0, cv = 0;
  if (sscanf(c->server.out.data, "READY %31s %31s %31s%n", ptext, ctext, etext,
             &consumed) != 3 ||
      unsigned_value(ptext, INT_MAX, &pv) ||
      unsigned_value(ctext, INT_MAX, &cv) || pv != (unsigned)c->server.pid ||
      strcmp(etext, "1") || c->server.out.data[consumed] != '\n') {
    c->error = "invalid server greeting";
    goto finish;
  }
  server_pid = (long)pv;
  chid = (int)cv;
  for (size_t i = 0; i < ncall; i++) {
    char pidstr[32], chstr[32], epochstr[32], idstr[32], work[32], timeout[32];
    snprintf(pidstr, sizeof(pidstr), "%ld", server_pid);
    snprintf(chstr, sizeof(chstr), "%d", chid);
    snprintf(epochstr, sizeof(epochstr), "%" PRIu64, epoch);
    snprintf(idstr, sizeof(idstr), "%zu", i + 1);
    snprintf(work, sizeof(work), "%u", calls[i].work);
    snprintf(timeout, sizeof(timeout), "%u", calls[i].timeout);
    char *args[] = {binaries[1], pidstr, chstr,   epochstr,
                    idstr,       work,   timeout, NULL};
    if (spawn_child(&c->current, args, -1)) {
      c->error = "client launch failed";
      goto finish;
    }
    attempted = i + 1;
    pids[i] = c->current.pid;
    int rc = wait_current(c, 7000);
    exits[i] = c->current.status;
    snprintf(name, sizeof(name), "client-%zu", i + 1);
    if (save_child(dir, name, &c->current)) {
      c->error = "cannot save client output";
      goto finish;
    }
    snprintf(name, sizeof(name), "client-%zu.stdout", i + 1);
    add_file(files, &file_count, name);
    snprintf(name, sizeof(name), "client-%zu.stderr", i + 1);
    add_file(files, &file_count, name);
    if (rc)
      goto finish;
    init_child(&c->current);
    if (c->server.reaped) {
      c->error = "server stopped before all calls";
      goto finish;
    }
  }
  if (!c->server.reaped)
    (void)kill(c->server.pid, SIGTERM);
  {
    uint64_t d = bounded_deadline(c, 3000);
    while (!finished(&c->server) || !c->effect_eof) {
      if (pump(c, d, false))
        goto finish;
    }
  }
  if (c->server.status) {
    c->error = "unclean server exit";
    goto finish;
  }
  status = "COMPLETE";
  code = 0;
finish:
  terminate_child(&c->current);
  terminate_child(&c->server);
  if (attempted && c->current.pid == pids[attempted - 1])
    exits[attempted - 1] = c->current.status;
  /* Final bounded drain. Cleanup does not convert a forced exit to success. */
  if (!c->error) {
    uint64_t d = now_ns() + UINT64_C(100000000);
    while (c->effect_fd >= 0 && !c->effect_eof && now_ns() < d)
      if (pump(c, d, true))
        break;
  }
  c->server_exit = c->server.status;
  if (c->current.pid > 0 && !c->current.reaped) {
    c->error = "client could not be reaped";
  }
  if (c->server.pid > 0 && !c->server.reaped) {
    c->error = "server could not be reaped";
  }
  if (c->effects) {
    c->observer_exit =
        (!c->error && c->effect_eof && c->effect_used == 0) ? 0 : 2;
    fprintf(c->effects,
            "{\"kind\":\"end\",\"complete\":%s,\"effect_count\":%zu,"
            "\"monotonic_ns\":%" PRIu64 "}\n",
            c->observer_exit == 0 ? "true" : "false", c->effect_count,
            now_ns());
    if (fclose(c->effects)) {
      c->error = "effect log close failed";
      c->observer_exit = 2;
    }
    c->effects = NULL;
  }
  close_stream(&c->current.out);
  close_stream(&c->current.err);
  close_stream(&c->server.out);
  close_stream(&c->server.err);
  if (c->effect_fd >= 0) {
    close(c->effect_fd);
    c->effect_fd = -1;
  }
  if (c->server.pid > 0) {
    if (save_child(dir, "server", &c->server)) {
      c->error = "cannot save server output";
    } else {
      add_file(files, &file_count, "server.stdout");
      add_file(files, &file_count, "server.stderr");
    }
    if (!path_join(path, dir, "server.jsonl") && access(path, F_OK) == 0)
      add_file(files, &file_count, "server.jsonl");
  }
  if (hashed) {
    FILE *f = new_file(dir, "binaries.json");
    if (!f)
      c->error = "cannot save binary identity";
    else {
      fputs("{\"schema\":1,\"binaries\":{", f);
      for (int i = 0; i < 4; i++) {
        size_t bytes = 0;
        bool stable = dl_sha256_file(binaries[i], after[i], &bytes) == 0 &&
                      bytes == sizes[i] && !strcmp(after[i], before[i]);
        if (!stable)
          c->error = "binary identity changed during capture";
        fprintf(f, "%s\"%s\":{\"sha256\":\"%s\",\"bytes\":%zu,\"stable\":%s}",
                i ? "," : "", suffix[i], before[i], sizes[i],
                stable ? "true" : "false");
      }
      fputs("}}\n", f);
      if (fclose(f))
        c->error = "binary identity close failed";
      add_file(files, &file_count, "binaries.json");
    }
  }
  if (c->error) {
    status = "INCOMPLETE";
    code = 78;
  }
report: {
  FILE *f = new_file(dir, "capture.json");
  if (!f) {
    free(c);
    return 74;
  }
  fprintf(
      f,
      "{\"schema\":1,\"status\":\"%s\",\"evidence_origin\":\"%s\",\"system\":",
      status, origin);
  json_string(f, u.sysname);
  fputs(",\"release\":", f);
  json_string(f, u.release);
  fputs(",\"machine\":", f);
  json_string(f, u.machine);
  fprintf(f,
          ",\"collector_pid\":%ld,\"token\":\"%s\",\"policy\":", (long)getpid(),
          token);
  json_string(f, mode);
  fprintf(f,
          ",\"server_pid\":%ld,\"server_exit\":%d,\"observer_exit\":%d,"
          "\"server_reaped\":%s,\"current_reaped\":%s,\"qnx_executed\":%s,"
          "\"timeout_errnos\":[%d,%d],\"interrupted\":%d,\"calls\":[",
          (long)c->server.pid, c->server_exit, c->observer_exit,
          c->server.reaped ? "true" : "false",
          c->current.pid <= 0 || c->current.reaped ? "true" : "false",
          native && c->server.pid > 0 ? "true" : "false", ETIMEDOUT, ECANCELED,
          (int)interrupted);
  for (size_t i = 0; i < ncall; i++)
    fprintf(f,
            "%s{\"id\":%zu,\"work_ms\":%u,\"timeout_ms\":%u,\"attempted\":%s,"
            "\"pid\":%ld,\"exit\":%d}",
            i ? "," : "", i + 1, calls[i].work, calls[i].timeout,
            i < attempted ? "true" : "false", (long)pids[i], exits[i]);
  fputs("],\"error\":", f);
  if (c->error)
    json_string(f, c->error);
  else
    fputs("null", f);
  fputs("}\n", f);
  if (fclose(f))
    code = 74;
  add_file(files, &file_count, "capture.json");
}
  if (streaming && stream_bundle(dir, files, file_count))
    code = 74;
  if (temporary) {
    for (size_t i = 0; i < file_count; i++) {
      if (!path_join(path, dir, files[i]))
        unlink(path);
    }
    if (rmdir(dir))
      code = 74;
  }
  free(c);
  return code;
}
