# Maintenance

> Written for the engineer who inherits this system.

## Starting and Stopping

There are no services. Agent runs are short-lived processes; sandboxes are deleted by the script's exit trap. If a run is killed, leftover sandboxes named `dfa-<timestamp>` may remain: list and delete them with the `openshell sandbox` commands (exact list command: uncertain — verify with developer).

<!-- sources: sandbox/run-agent.sh -->

## Dependency Updates

Python dependencies: `typer>=0.12` and `anthropic` (unpinned) in `pyproject.toml`, locked in `uv.lock`. Update with uv, then run the tests and `docforge check`. Changing `pyproject.toml`/`uv.lock` triggers the strict `dependencies` drift rule, so update [DEPENDENCIES.md](DEPENDENCIES.md) in the same change. Model name and prices are hard-coded in `agent/budget.py`; update them together when changing the model. Sandbox images pin Node major 22, mermaid-cli 11, Ubuntu 24.04 and python 3.12; tectonic is unpinned.

<!-- sources: pyproject.toml, docforge.toml, src/docforge/agent/budget.py, sandbox/build.Dockerfile -->

## Database Migrations

Not applicable: no database. See [DATA_MODEL.md](DATA_MODEL.md).

<!-- sources: src/docforge/agent/budget.py -->

## Secret Rotation

The only secret is the Anthropic API key. On the host it is held by the OpenShell `anthropic` provider (created from `ANTHROPIC_API_KEY`; exact rotation command: uncertain — verify with developer). It is never placed in the sandbox. See [SECURITY.md](SECURITY.md).

<!-- sources: sandbox/anthropic-profile.yaml, sandbox/run-agent.sh -->

## Configuration Management

`docforge.toml` is version-controlled and reviewed like code. After changing the impact map, run `docforge check --strict`. The map in this repository was guessed by `docforge init` and flagged in its comment for review.

<!-- sources: docforge.toml -->

## Logs

Per agent run: `documentation/build/agent/{trace.log,policy.log,run.json}`. Spend: `~/.docforge/usage.jsonl` or `docforge usage`. OpenShell denials: `openshell logs <sandbox>` (used by `redteam.sh`).

<!-- sources: src/docforge/agent/runner.py, sandbox/redteam.sh -->

## Backups

Nothing to back up except the usage ledger `~/.docforge/usage.jsonl`, which enforces the monthly cap; losing it resets the month's tally to zero.

<!-- sources: src/docforge/agent/budget.py -->

## Releases

No release automation. The manual build job runs on tag refs and the version string comes from `git describe`. Package version is `0.1.0`. Bumping it changes the image tags used by `run-agent.sh` and `redteam.sh`.

<!-- sources: .github/workflows/docforge.yml, pyproject.toml, sandbox/run-agent.sh -->

## Making Production Changes

Not a service. For changes: run tests and lint ([TESTING.md](TESTING.md)); if you touch policy, budget, apply or sandbox files run `sandbox/redteam.sh`; add a `Docs-Impact` trailer or update the mapped docs.

<!-- sources: docforge.toml, sandbox/redteam.sh -->

## Known Technical Debt

- CI installs docforge from `main` of github.com/beese54/docforge (unpinned). Pin it to a tag once releases exist, so a docforge change cannot break other repos' CI.
- The build-sandbox red-team checks (5.4, 5.4b) still needed a rerun under OpenShell at that date.
- No CI job runs pytest, ruff or mypy (workflow only runs `docforge check` and the manual build).
- Prices and model id are hard-coded.
- Agent impact runs did not add `sources` comments to CHANGELOG entries (status note).

<!-- sources: STATUS-2026-09-30.md, .github/workflows/docforge.yml, src/docforge/agent/budget.py -->

## Fragile Areas

### Fragile area: Policy enforcement point

- Component: `agent/policy.py`, `apply.py`, `config.AGENT_WRITABLE`
- Why it is sensitive: the only barrier between model output and the repository.
- What depends on it: the guarantee that agent patches only touch docs.
- What must be tested before changing it: `tests/test_agent.py`, `tests/test_apply.py`, `sandbox/redteam.sh`.
- Relevant files: `src/docforge/agent/policy.py`, `src/docforge/apply.py`
- Relevant ADR: [ADR-001](adr/001-human-reviewed-patches-only.md)

### Fragile area: Budget guard

- Component: `agent/budget.py`
- Why it is sensitive: hard-coded prices; wrong values silently defeat the cap.
- What must be tested before changing it: `tests/test_agent.py`.
- Relevant ADR: [ADR-002](adr/002-budget-guard-and-manual-agent-loop.md)

### Fragile area: Streaming retry in the runner

- Component: `agent/runner.py`
- Why it is sensitive: it imports `httpx2`, described as the SDK's HTTP client, but `httpx2` is not a direct dependency in `pyproject.toml` (uncertain — verify with developer). A dropped stream is retried only for connection/transport errors.

### Fragile area: PDF build environment

- Component: `build.py`, `docforge.lua`, `sandbox/build.Dockerfile`
- Why it is sensitive: depends on pandoc/tectonic/Chromium; Chromium needs `--no-zygote` under OpenShell seccomp; exec sessions do not inherit image ENV.
- Relevant ADR: [ADR-006](adr/006-pandoc-tectonic-manual-pipeline.md)

<!-- sources: src/docforge/agent/policy.py, src/docforge/agent/runner.py, src/docforge/agent/budget.py, pyproject.toml, sandbox/build.Dockerfile, sandbox/build-policy.yaml -->
