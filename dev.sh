#!/usr/bin/env bash
# Run a command in the docforge dev environment: ./dev.sh pytest -q
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/docforge}"
exec uv run "$@"
