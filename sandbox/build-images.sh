#!/usr/bin/env bash
# Build the docforge wheel and both sandbox images. Run from anywhere inside WSL/Linux.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH" UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/docforge}"
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)

rm -rf dist && uv build --wheel -q
docker build -f sandbox/agent.Dockerfile -t "docforge-agent:$VERSION" .
docker build -f sandbox/build.Dockerfile -t "docforge-build:$VERSION" .
docker images | grep docforge
