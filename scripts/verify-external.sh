#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if ! command -v nginx >/dev/null 2>&1; then
    echo 'NOT RUN: optional independent-target check requires a locally installed nginx.' >&2
    exit 77
fi
if ! nginx -V 2>&1 | grep -q -- '--with-http_dav_module'; then
    echo 'NOT RUN: nginx was not built with its DAV module.' >&2
    exit 77
fi
mkdir -p artifacts
OUT="artifacts/external-verify-$(date -u +%Y%m%dT%H%M%SZ)-$$"
python3 -S -m deadline_lab external-regress regressions/external/suite.json \
    --out "$OUT" --sensitivity
printf '\nIndependent nginx-target regression evidence: %s\n' "$OUT"
printf 'This does not build or run QNX and does not operate physical devices.\n'
