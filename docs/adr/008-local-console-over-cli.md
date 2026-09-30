# ADR-008: A local-only console over the CLI, with guarded push and PR buttons

## Status

Accepted

## Context

docforge needed a UI for demonstrations. Everything it does already exists as CLI commands and sandbox scripts, and the safety of the system rests on properties of those paths (the agent runs only in OpenShell, `apply` re-checks paths, a human decides every publish). The owner chose three things on 2026-09-30: local only, replay mode for demos, and push plus open-PR buttons in the UI.

## Options Considered

- **Hosted web app.** Reachable anywhere, but it would need real authentication, a server with OpenShell, and custody of GitHub credentials. Rejected for a demo tool.
- **Local web UI that reimplements the logic.** Faster screens, but two implementations would drift, and the UI could bypass the sandbox or the path checks.
- **Local web UI over the existing functions and scripts** (chosen). Every action calls `checks`, `drift`, `build`, `apply`, `sandbox/run-agent.sh` or `sandbox/redteam.sh`.
- **For publishing:** leave push to the developer's terminal, or add buttons with guards. The owner asked for buttons; the guards keep the same boundary a careful developer would.

## Decision

`docforge serve` runs a FastAPI app on 127.0.0.1 only, as an optional `[console]` extra.

- Security: a Host-header check, a per-launch token (cookie for pages, header for actions) and no stored secrets.
- Runs: replays of three real recorded runs are the default; live runs are one at a time through `run-agent.sh`.
- Publishing: Apply, Push and Open PR appear one step at a time. Push is limited to `docforge/*` branches this console created, with an explicit refspec and never force.

## Rationale

- One implementation of every rule: the console cannot show different results from `docforge check`, and a live run from the browser is exactly a sandboxed CLI run.
- A local app still faces the browser threat model. DNS rebinding and cross-site requests are real attacks on localhost services, and the Host check plus token header stop them without adding user accounts.
- Replays make demos free and repeatable, and they cannot change anything.
- Publishing stays a human decision: the confirm screen shows exactly what leaves the machine, and the branch name comes from server state, never from the browser.

<!-- sources: src/docforge/console/app.py, src/docforge/console/runs.py, src/docforge/console/publish.py, specification.json, definition_of_done.md -->

## Consequences

- Adds FastAPI, uvicorn, Jinja2 and python-multipart as an optional extra (see [DEPENDENCIES.md](../DEPENDENCIES.md)).
- The console must be started from the docforge checkout for live runs, because it calls the `sandbox/` scripts.
- In WSL, pushing needs git's credential helper pointed at the Windows Git Credential Manager; PRs use the Windows `gh.exe`.
- Run history is in memory and is lost when the console stops; outputs on disk remain.

## Related Components

`src/docforge/console/`, `src/docforge/cli.py` (`serve`), `sandbox/run-agent.sh`, `sandbox/redteam.sh`, [SECURITY.md](../SECURITY.md), [API.md](../API.md), [DEMO.md](../DEMO.md)
