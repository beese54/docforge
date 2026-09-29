#!/usr/bin/env bash
# Environment check for docforge development (run inside WSL/Linux).
# Non-destructive: reports what is missing, installs nothing.
set -u
export PATH="$HOME/.local/bin:$PATH"
missing=0

need() {  # name, min-version-hint
  if command -v "$1" >/dev/null 2>&1; then
    printf '  ok       %-10s %s\n' "$1" "$("$1" --version 2>/dev/null | head -1)"
  else
    printf '  MISSING  %-10s %s\n' "$1" "$2"; missing=1
  fi
}

echo "docforge prerequisites:"
need python3  "python 3.12+"
need uv       "curl -LsSf https://astral.sh/uv/install.sh | sh"
need git      "apt install git"
need pandoc   "apt install pandoc (>= 3)"
need tectonic "https://tectonic-typesetting.github.io"
need node     "Node.js >= 20 (mermaid-cli's puppeteer rejects 18)"
need mmdc     "npm install -g @mermaid-js/mermaid-cli, then in its package dir: npx puppeteer browsers install chrome-headless-shell (needs unzip)"
need pdftotext "apt install poppler-utils"
need docker   "Docker Desktop with WSL integration"
need openshell "https://github.com/NVIDIA/OpenShell"

if [ "$missing" -ne 0 ]; then echo "init.sh: missing prerequisites"; exit 1; fi

# Keep the virtualenv off OneDrive-synced paths.
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/docforge}"
uv sync --quiet || { echo "init.sh: uv sync failed"; exit 1; }
echo "init.sh: environment ready (venv: $UV_PROJECT_ENVIRONMENT)"
