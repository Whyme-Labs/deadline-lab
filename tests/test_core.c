#include "dl_core.h"
#include <stdio.h>
#include <stdlib.h>
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); exit(1); } } while (0)
int main(void) {
    dl_state s;
    dl_command c = {1, 1, 100, 200, 3}, effect;
    unsigned checks = 0;
#define EXPECT(call, expected) do { CHECK((call) == (expected)); ++checks; } while (0)
    dl_init(&s, 1, 0);
    EXPECT(dl_prepare(&s, &c), DL_OK);
    EXPECT(dl_commit(&s, 1, 199, &effect), DL_APPLY);
    CHECK(effect.delta == 3);
    EXPECT(dl_prepare(&s, &c), DL_OK);
    EXPECT(dl_commit(&s, 1, 199, &effect), DL_DUPLICATE);
    EXPECT(dl_cancel(&s, 1), DL_TOO_LATE);
    dl_init(&s, 1, 0);
    EXPECT(dl_prepare(&s, &c), DL_OK);
    EXPECT(dl_commit(&s, 1, 200, &effect), DL_EXPIRED);
    EXPECT(dl_prepare(&s, &c), DL_OK);
    EXPECT(dl_commit(&s, 1, 99, &effect), DL_INVALID);
    dl_init(&s, 2, 0);
    EXPECT(dl_prepare(&s, &c), DL_OK);
    EXPECT(dl_commit(&s, 1, 110, &effect), DL_WRONG_EPOCH);
    dl_init(&s, 1, 0);
    EXPECT(dl_prepare(&s, &c), DL_OK);
    EXPECT(dl_cancel(&s, 1), DL_OK);
    EXPECT(dl_commit(&s, 1, 110, &effect), DL_CANCELLED);
    EXPECT(dl_prepare(&s, &c), DL_OK);
    EXPECT(dl_commit(&s, 1, 110, &effect), DL_CANCELLED);
    c.delta = 4;
    EXPECT(dl_prepare(&s, &c), DL_CONFLICT);
    c.delta = 3;
    dl_init(&s, 1, 0);
    EXPECT(dl_commit(&s, 1, 110, &effect), DL_NO_PENDING);
    EXPECT(dl_cancel(&s, 1), DL_NO_PENDING);
    EXPECT(dl_prepare(&s, &c), DL_OK);
    c.id = 2;
    EXPECT(dl_prepare(&s, &c), DL_BUSY);
    dl_abandon(&s);
    EXPECT(dl_prepare(&s, &c), DL_OK);
    dl_abandon(&s);
    c.id = 0;
    EXPECT(dl_prepare(&s, &c), DL_INVALID);
    c.id = 3; c.delta = 0;
    EXPECT(dl_prepare(&s, &c), DL_INVALID);
    c.delta = 1; c.expires_ns = c.issued_ns;
    EXPECT(dl_prepare(&s, &c), DL_INVALID);
    dl_init(&s, 1, 0);
    c.expires_ns = 200;
    for (uint64_t id = 1; id <= DL_CAPACITY; ++id) {
        c.id = id;
        EXPECT(dl_prepare(&s, &c), DL_OK);
        EXPECT(dl_commit(&s, id, 150, &effect), DL_APPLY);
    }
    c.id = DL_CAPACITY + 1;
    EXPECT(dl_prepare(&s, &c), DL_CAPACITY_FULL);
    c.id = 1;
    EXPECT(dl_prepare(&s, &c), DL_OK);
    EXPECT(dl_commit(&s, 1, 150, &effect), DL_DUPLICATE);
    printf("core_checks=%u\n", checks);
    return 0;
}
