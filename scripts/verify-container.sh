#!/bin/sh
# Reproduce the Linux checks on a Mac or Linux host with a running Docker engine.
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
image_name=deadline-lab-validation:ubuntu24.04
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo 'NOT RUN: start your Docker-compatible engine, then rerun this command.' >&2
  exit 77
fi

# The SDK, licence, credentials and home directory are never build inputs.
docker build --platform linux/amd64 -t "$image_name" - <<'DOCKERFILE'
FROM ubuntu:24.04@sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential cmake python3 nginx ca-certificates file git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
DOCKERFILE

# Application traffic stays on container loopback. Only this project is mounted.
docker run --rm --platform linux/amd64 --network none \
  --mount "type=bind,source=$project_root,target=/workspace" \
  --workdir /workspace "$image_name" sh -eu -c '
    ./scripts/verify-local.sh
    ./scripts/verify-external.sh
    ./scripts/verify-capture.sh
    ./scripts/verify-offline.sh
  '
echo 'Linux verification complete. QNX compilation and execution remain separate.'
