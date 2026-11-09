#include "dl_core.h"
#include <string.h>

void dl_init(dl_state *s, uint64_t epoch, unsigned mutation) {
    memset(s, 0, sizeof(*s));
    s->epoch = epoch;
    s->mutation = mutation;
}

static bool identical(const dl_command *a, const dl_command *b) {
    return a->id == b->id && a->epoch == b->epoch &&
        a->issued_ns == b->issued_ns && a->expires_ns == b->expires_ns &&
        a->delta == b->delta;
}

dl_result dl_prepare(dl_state *s, const dl_command *c) {
    if (c->id == 0 || c->epoch == 0 || c->issued_ns == 0 ||
        c->expires_ns <= c->issued_ns || c->delta < -1000000 ||
        c->delta > 1000000 || c->delta == 0) return DL_INVALID;
    if (s->pending && s->records[s->pending_index].command.id != c->id)
        return DL_BUSY;
    size_t index = 0;
    while (index < s->count && s->records[index].command.id != c->id) ++index;
    if (index < s->count && !identical(&s->records[index].command, c))
        return DL_CONFLICT;
    if (index == s->count) {
        /* Never silently evict a cancellation or deduplication tombstone. */
        if (s->count == DL_CAPACITY) return DL_CAPACITY_FULL;
        s->records[index].command = *c;
        s->records[index].applied = false;
        s->records[index].cancelled = false;
        ++s->count;
    }
    s->pending = true;
    s->pending_index = index;
    return DL_OK;
}

dl_result dl_cancel(dl_state *s, uint64_t id) {
    for (size_t i = 0; i < s->count; ++i) {
        if (s->records[i].command.id != id) continue;
        if (s->records[i].applied) return DL_TOO_LATE;
        s->records[i].cancelled = true;
        return DL_OK;
    }
    return DL_NO_PENDING;
}

dl_result dl_commit(dl_state *s, uint64_t id, uint64_t now_ns, dl_command *effect) {
    if (!s->pending || s->records[s->pending_index].command.id != id)
        return DL_NO_PENDING;
    dl_record *r = &s->records[s->pending_index];
    s->pending = false;
    if (s->mutation & DL_DENY_ALL) return DL_REJECT_ALL;
    if (now_ns < r->command.issued_ns) return DL_INVALID;
    if (!(s->mutation & DL_OMIT_EPOCH) && r->command.epoch != s->epoch)
        return DL_WRONG_EPOCH;
    /* Equality is expired. The validity interval is half-open. */
    if (!(s->mutation & DL_OMIT_EXPIRY) && now_ns >= r->command.expires_ns)
        return DL_EXPIRED;
    if (!(s->mutation & DL_OMIT_CANCEL) && r->cancelled) return DL_CANCELLED;
    if (!(s->mutation & DL_OMIT_DEDUPE) && r->applied) return DL_DUPLICATE;
    r->applied = true;
    *effect = r->command;
    return DL_APPLY;
}

void dl_abandon(dl_state *s) { s->pending = false; }

const char *dl_result_name(dl_result r) {
    static const char *names[] = {
        "ok", "apply", "no_pending", "busy", "invalid", "conflict",
        "wrong_epoch", "expired", "cancelled", "duplicate", "capacity_full",
        "too_late", "reject_all"
    };
    if ((unsigned)r >= sizeof(names) / sizeof(names[0])) return "unknown";
    return names[r];
}

int dl_parse_mode(const char *name, unsigned *mode) {
    static const struct { const char *name; unsigned bits; } modes[] = {
        {"reference", 0}, {"omit_epoch", DL_OMIT_EPOCH},
        {"omit_expiry", DL_OMIT_EXPIRY}, {"omit_cancel", DL_OMIT_CANCEL},
        {"omit_dedupe", DL_OMIT_DEDUPE}, {"reject_all", DL_DENY_ALL}
    };
    for (size_t i = 0; i < sizeof(modes) / sizeof(modes[0]); ++i)
        if (strcmp(name, modes[i].name) == 0) { *mode = modes[i].bits; return 0; }
    return -1;
}
