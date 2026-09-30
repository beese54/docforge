# Dependencies

> Dependencies that would be hard to replace or could significantly affect the application.

## Critical Dependencies

### Anthropic API and `anthropic` SDK

- Purpose: model calls for the agent.
- Current version: SDK unpinned in `pyproject.toml`; resolved version is in `uv.lock` (not read). Model `claude-sonnet-5-5`, hard-coded.
- Why it is used: the only model provider implemented.
- Replacement difficulty: high. The runner uses streaming, `count_tokens`, adaptive thinking, `output_config`, prompt caching and strict tool schemas; prices are hard-coded per model in `budget.py`.
- Upgrade considerations: the runner imports `httpx2` (the SDK's HTTP client) to catch a stream cut mid-body (`httpx2.RemoteProtocolError`, which the SDK does not wrap). `httpx2` is therefore declared as a direct dependency in `pyproject.toml`, so an SDK change of HTTP client cannot silently break that import. The runner also catches `TypeError` for missing credentials. Both depend on SDK internals, so re-run `tests/test_agent.py` after any SDK upgrade.
- Known limitations: costs come from a price table copied on 2026-09-25 (per its comment); it may go stale.

### OpenShell

- Purpose: sandbox runtime enforcing filesystem and egress policy for the agent and the build.
- Current version: 0.1.x (per `anthropic-profile.yaml`, which notes it ships no profiles).
- Replacement difficulty: high; policy files and `run-agent.sh` use its CLI. See [ADR-003](adr/003-openshell-sandboxes.md).
- Known limitations: needs a Docker engine reachable by its gateway; landlock is `best_effort`.

### pandoc, tectonic, mermaid-cli

- Purpose: PDF manual. pandoc 3.1.3 from Ubuntu 24.04 in the build image; tectonic unpinned; mermaid-cli 11; Node 22.
- Replacement difficulty: medium; the Lua filter is pandoc-specific. See [ADR-006](adr/006-pandoc-tectonic-manual-pipeline.md).

### Typer

- Purpose: CLI framework (`typer>=0.12`). Low-to-medium replacement effort; only `cli.py` uses it.

### git CLI

- Purpose: drift detection, diffing, apply and versioning, all through `git.py`. Assumed installed; a missing git raises `GitError`.

### uv / hatchling

- Purpose: environment and build (`uv sync`, `uv build --wheel`); CI uses `uvx`.

### FastAPI, uvicorn, Jinja2, python-multipart (optional `[console]` extra)

- Purpose: docforge Console only (`docforge serve`). Installed with `pip install 'docforge[console]'`, and also in the `dev` group so tests cover them. CI's `uvx` install does not pull them in, so the docs check stays small.
- Current version: fastapi 0.142, uvicorn 0.54, Jinja2 3.1 (see `uv.lock`).
- Replacement difficulty: low to medium. Routes and middleware are in `console/app.py`; templates are plain Jinja2; the browser code is dependency-free.
- Upgrade considerations: re-run `tests/test_console*.py`. The security middleware (Host check, session cookie, action token) relies on Starlette's `BaseHTTPMiddleware` and cookie handling.

### httpx (dev only)

- Purpose: FastAPI's `TestClient` needs it for the console tests. The runtime uses the SDK's `httpx2` instead.

### GitHub CLI (`gh`) and Git Credential Manager (console publishing)

- Purpose: the console's Open PR button runs `gh pr create`, and its Push button runs `git push` with the developer's existing login. In WSL the console uses the Windows `gh.exe` when no Linux `gh` is installed (override with `DOCFORGE_GH`), and git's credential helper points at the Windows Git Credential Manager.
- Replacement difficulty: low. Both calls are in `console/publish.py`.

<!-- sources: pyproject.toml, uv.lock, src/docforge/agent/budget.py, src/docforge/agent/runner.py, src/docforge/console/app.py, src/docforge/console/publish.py, sandbox/anthropic-profile.yaml, sandbox/build.Dockerfile, src/docforge/git.py, init.sh -->
