#!/bin/sh
set -eu
if ! command -v qcc >/dev/null 2>&1; then
    echo 'BLOCKED: licensed QNX qcc is not available. No mock or host build counts as QNX evidence.' >&2
    exit 77
fi
: "${QNX_HOST:?Source the QNX SDK environment first}"
: "${QNX_TARGET:?Source the QNX SDK environment first}"
cmake -S . -B build-qnx -DCMAKE_TOOLCHAIN_FILE=qnx/toolchain.cmake \
    -DDL_QNX_VARIANT="${DL_QNX_VARIANT:-gcc_ntox86_64}"
cmake --build build-qnx -j2
