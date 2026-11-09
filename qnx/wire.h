#ifndef DL_QNX_WIRE_H
#define DL_QNX_WIRE_H
#include "dl_core.h"
#define DL_QNX_MAGIC UINT32_C(0x444c3031)
/* Local-only same-build ABI. Not a serialised cross-machine network protocol. */
typedef struct {
    uint32_t magic, version, work_ms, reserved;
    dl_command command;
} dl_qnx_request;
typedef struct { uint32_t version, result; uint64_t id; } dl_qnx_reply;
#endif
