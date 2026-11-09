#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for tool in cmake cc python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing local dependency: $tool" >&2; exit 2; }
done
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build -j2
ctest --test-dir build --output-on-failure
python3 -S -m unittest discover -s tests -p 'test_*.py' -v
mkdir -p artifacts
OUT="artifacts/verify-$(date -u +%Y%m%dT%H%M%SZ)-$$"
python3 -S -m deadline_lab regress regressions/suite.json --out "$OUT" --verify-mutants
printf '\nLocal verification complete. Regression evidence: %s\n' "$OUT"
printf 'QNX compilation/execution is a separate gate and was not run by this command.\n'
printf 'Optional nginx execution tests are skipped when nginx is absent; verify-external.sh requires them.\n'
