#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j2
ctest --test-dir build --output-on-failure
python3 -S -m unittest discover -s tests -p 'test_capture.py' -v
OUT="artifacts/capture-$(date -u +%Y%m%dT%H%M%SZ)-$$"
python3 -S -m deadline_lab.capture_campaign --bin build --out "$OUT" --repetitions 1
printf '\nC collector transport verified locally. Evidence: %s\n' "$OUT"
printf 'This command never compiles QNX, emulates its APIs or opens an SSH connection.\n'
