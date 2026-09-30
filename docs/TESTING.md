# Testing

> Testing strategy and what must pass before a change is accepted.

## Strategy

pytest suite under `tests/`, one file per module area. Tests use temporary git repositories and an isolated usage ledger (autouse fixture sets `DOCFORGE_HOME`), so they never touch `~/.docforge`. Static checks: ruff (line length 120, rules E,F,W,I,B,UP,SIM) and mypy in strict mode. Test contents were not read in detail beyond `conftest.py` and `test_smoke.py`; file names indicate coverage of agent, apply, build, checks, config, drift, init and templates (uncertain — verify with developer what each covers).

<!-- sources: tests/conftest.py, tests/test_smoke.py, pyproject.toml, tests/ (file listing) -->

## Unit Tests

`tests/test_config.py`, `test_checks.py`, `test_drift.py`, `test_init.py`, `test_templates.py`, `test_build.py`, `test_apply.py`, `test_agent.py`, `test_smoke.py` (CLI `--version`). The runner accepts a fake client (see `run(client: Any ...)` comment), which suggests the agent is tested without the network.

<!-- sources: tests/, src/docforge/agent/runner.py -->

## Integration Tests

The `repo` fixture creates a real git repository, so git-dependent code is exercised with the real git CLI. No dedicated integration suite is defined.

<!-- sources: tests/conftest.py -->

## End-to-End Tests

None automated. Manual pilot runs are recorded in `evidence/` (not reviewed here).

<!-- sources: evidence/ (file listing) -->

## Security Tests

`sandbox/redteam.sh` runs live attacks against the OpenShell sandboxes: key absence (5.1), key swap works only for Anthropic (5.1b), blocked egress (5.2, 5.2b), read-only system paths (5.3, 5.3b), build sandbox offline (5.4, 5.4b). Needs docker, openshell and images; the only API request is the free `GET /v1/models`. `--agent-only` skips build-sandbox checks.

<!-- sources: sandbox/redteam.sh -->

## Manual and Smoke Tests

`docforge check --strict` on this repository; `docforge build --format tex` to inspect LaTeX; `docforge build --strict` to ensure Mermaid renders (the image build does this with `sandbox/warmup`).

<!-- sources: src/docforge/cli.py, sandbox/build.Dockerfile -->

## Test Environments and Data

Local WSL/Linux via `./init.sh`. `sandbox/warmup/` is a fixture manual. `git` must be installed.

<!-- sources: init.sh, sandbox/build.Dockerfile -->

## Running Tests

```bash
./dev.sh pytest -q
./dev.sh ruff check .
./dev.sh mypy src
sandbox/redteam.sh --agent-only   # needs images + OpenShell
```

<!-- sources: dev.sh, pyproject.toml, sandbox/redteam.sh -->

## Required Before Changes

- `pytest` passes; ruff and mypy clean (no CI job enforces this: see [MAINTENANCE.md](MAINTENANCE.md#known-technical-debt)).
- `docforge check --strict` passes (the only thing CI enforces).
- Changes to policy/budget/apply/sandbox files: rerun `sandbox/redteam.sh`.

<!-- sources: .github/workflows/docforge.yml, docforge.toml -->
