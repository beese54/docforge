# Design

> Design intent: boundaries, abstractions and conventions, not a file listing.

## Design Principles

- **The model proposes, a human disposes.** The agent never writes to disk in the repository; see [ADR-001](adr/001-human-reviewed-patches-only.md).
- **Enforce by construction, not by prompt.** Path limits and spend caps are code, not instructions ([ADR-002](adr/002-budget-guard-and-manual-agent-loop.md)).
- **Deterministic checks are separate from the model.** `check` never uses the network ([ADR-004](adr/004-deterministic-checks-in-ci.md)).
- **Honesty markers.** Unverified claims are written "uncertain — verify with developer" and counted by `check`.
- **One source of truth for the doc set.** `doctypes.py` drives scaffolding, checking and the agent prompt.

<!-- sources: src/docforge/agent/policy.py, src/docforge/agent/budget.py, src/docforge/doctypes.py, src/docforge/checks.py -->

## Component Boundaries

- `cli.py` only wires commands; logic sits in per-command modules, imported lazily inside each command.
- All repository access by the agent goes through `agent/policy.py:ToolLayer`. All git access goes through `git.py`.
- `apply.py` runs on the host and does not trust the patch: it re-validates every path.
- Sandboxes: the agent has network only to api.anthropic.com; the PDF build has none ([ADR-003](adr/003-openshell-sandboxes.md)).

<!-- sources: src/docforge/cli.py, src/docforge/agent/policy.py, src/docforge/apply.py, src/docforge/git.py -->

## Key Abstractions and Patterns

- `Config` / `ImpactRule`: the impact map (globs to docs, optionally `adr_worthy`) ([ADR-005](adr/005-impact-map-drift-detection.md)).
- `Finding` with severity (info/warn/error) and a `Check` = function of `Context`; `checks.run` accepts extra checks (drift is injected this way).
- `ToolLayer`: stages writes in a dict, records denials as `PolicyEvent`s.
- `BudgetGuard`: sizes `max_tokens` so the worst case fits the remaining allowance; interrupted streams are charged worst-case.
- Escape hatch: a `Docs-Impact: none — <reason>` commit trailer; an empty reason is reported and ignored.
- Build pipeline: pandoc plus a Lua filter that turns Mermaid blocks into figures and rewrites cross-file links ([ADR-006](adr/006-pandoc-tectonic-manual-pipeline.md)).

<!-- sources: src/docforge/config.py, src/docforge/checks.py, src/docforge/drift.py, src/docforge/agent/policy.py, src/docforge/agent/budget.py, src/docforge/templates/docforge.lua -->

## Configuration Strategy

A single `docforge.toml` at the repository root. Unknown keys are errors so typos cannot silently disable a check. Sections: `[project]`, `[docs]`, `[[impact]]`, `[manual]`, `[budget]`, `[uncertain]`. The agent write allowlist (`README.md`, `CHANGELOG.md`, `docs/**`) is deliberately not configurable. Environment: `DOCFORGE_HOME` (ledger location), `ANTHROPIC_API_KEY`, `DOCFORGE_PUPPETEER_CONFIG` (Mermaid). Build defaults can be overridden by `documentation/manual.yaml` and `documentation/templates/manual-header.tex`.

<!-- sources: src/docforge/config.py, src/docforge/build.py, src/docforge/agent/budget.py -->

## Error Handling

Each layer raises its own exception (`ConfigError`, `GitError`, `ToolError`, `AgentError`, `BudgetExceeded`, `BuildError`, `ApplyError`) which `cli.py` maps to exit codes: 2 = configuration/environment, 3 = agent failure or missing credentials, 1 = check errors, patch refused or build content failure. Tool denials go back to the model as error results rather than aborting. On any agent failure `docforge.patch` and `report.md` are deleted, `trace.log`, `policy.log`, `run.json` are kept, and finished documents are saved in `docforge.partial.patch`. Stream drops are retried 3 times with backoff.

<!-- sources: src/docforge/cli.py, src/docforge/agent/runner.py, src/docforge/build.py -->

## Logging

There is no logging framework. Agent runs write `trace.log` (per-turn cost and tool calls), `policy.log` (denials) and `run.json` into the output directory; spend is appended to `usage.jsonl`. Other commands print to stdout/stderr.

<!-- sources: src/docforge/agent/runner.py, src/docforge/agent/budget.py -->

## Authentication and Authorisation

Only outbound: the Anthropic SDK reads credentials from the environment; inside the sandbox a placeholder key is swapped for the real one at egress. There are no users or roles. "Authorisation" is the path policy. See [SECURITY.md](SECURITY.md).

<!-- sources: src/docforge/cli.py, sandbox/anthropic-profile.yaml -->

## State Management

Stateless apart from the append-only usage ledger and run outputs. The monthly cap is computed from the ledger at run start, so it spans runs, including sandboxed ones (the script copies the ledger in and out).

<!-- sources: src/docforge/agent/budget.py, sandbox/run-agent.sh -->

## API Conventions

The public interface is the CLI ([API.md](API.md)). `--path` selects the repository root; `check` supports `--format json`; `--base` selects the drift baseline.

<!-- sources: src/docforge/cli.py -->
