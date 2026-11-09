#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec python3 -S -m deadline_lab.native_workflow accept "$@"
