#ifndef DL_EFFECT_H
#define DL_EFFECT_H
#include "dl_core.h"
/* Dedicated pipe to the separate virtual-effect observer. This is NOT a device IO API. */
int dl_emit_effect(int fd, const dl_command *effect, uint64_t epoch,
                   uint64_t attempt, uint64_t commit_ns);
#endif
