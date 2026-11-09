#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if ! command -v python3 >/dev/null 2>&1; then
    echo 'NOT_RUN: this host-side build helper requires Python 3.10 or newer.' >&2
    exit 77
fi
if [ "$#" -eq 0 ]; then
    set -- --out "artifacts/qnx-build-$(date -u +%Y%m%dT%H%M%SZ)-$$"
fi
exec python3 -S -m deadline_lab.native_build "$@"
