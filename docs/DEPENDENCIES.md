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

<!-- sources: pyproject.toml, src/docforge/agent/budget.py, src/docforge/agent/runner.py, sandbox/anthropic-profile.yaml, sandbox/build.Dockerfile, src/docforge/git.py, init.sh -->
