#ifndef DL_CORE_H
#define DL_CORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* No OS dependencies. This is a bounded teaching fixture, not a motor driver. */
#define DL_CAPACITY 512u
#define DL_SCHEMA 1u

typedef struct {
    uint64_t id, epoch, issued_ns, expires_ns;
    int32_t delta;
} dl_command;

typedef enum {
    DL_OK, DL_APPLY, DL_NO_PENDING, DL_BUSY, DL_INVALID, DL_CONFLICT,
    DL_WRONG_EPOCH, DL_EXPIRED, DL_CANCELLED, DL_DUPLICATE, DL_CAPACITY_FULL,
    DL_TOO_LATE, DL_REJECT_ALL
} dl_result;

enum {
    DL_OMIT_EPOCH = 1u, DL_OMIT_EXPIRY = 2u,
    DL_OMIT_CANCEL = 4u, DL_OMIT_DEDUPE = 8u, DL_DENY_ALL = 16u
};

typedef struct {
    dl_command command;
    bool cancelled, applied;
} dl_record;

typedef struct {
    uint64_t epoch;
    unsigned mutation;
    size_t count, pending_index;
    bool pending;
    dl_record records[DL_CAPACITY];
} dl_state;

void dl_init(dl_state *s, uint64_t epoch, unsigned mutation);
dl_result dl_prepare(dl_state *s, const dl_command *command);
dl_result dl_cancel(dl_state *s, uint64_t id);
dl_result dl_commit(dl_state *s, uint64_t id, uint64_t now_ns, dl_command *effect);
void dl_abandon(dl_state *s);
const char *dl_result_name(dl_result result);
int dl_parse_mode(const char *name, unsigned *mode);
#endif
