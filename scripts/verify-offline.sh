#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for tool in cmake cc python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing local dependency: $tool" >&2; exit 77; }
done
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j2
python3 -S -m unittest discover -s tests -p 'test_offline.py' -v
mkdir -p artifacts
OUT="artifacts/offline-$(date -u +%Y%m%dT%H%M%SZ)-$$"
python3 -S scripts/rehearse-offline.py --bin build --out "$OUT"
printf '\nOffline transport rehearsal complete. Evidence: %s\n' "$OUT"
printf 'Only a genuine native capture can establish native application behaviour.\n'
