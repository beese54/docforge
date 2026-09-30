# API

> Behaviour, assumptions and side effects that a generated API spec does not capture.

## Overview

The main interface is the `docforge` CLI (Typer). `--path` (repository root, default `.`) applies to all commands except `usage` and `serve`. `docforge --version` prints the version. The optional console (`docforge serve`) adds a local HTTP interface for the browser only; it is not a public API (see [Console HTTP routes](#console-http-routes)).

<!-- sources: src/docforge/cli.py -->

## Endpoints

### `docforge init`

- Purpose: create missing docs, config, CI workflow, ADR template.
- Side effects: writes files (never overwrites); may append to `.gitignore`.

### `docforge check [--strict] [--format text|json] [--base REF]`

- Purpose: run deterministic checks and drift detection.
- Side effects: none. Exit 0/1 (errors)/2 (bad config). Default base: merge-base with `origin/main`, `origin/master`, `main` or `master`.

### `docforge build [--out DIR] [--format pdf|tex] [--strict]`

- Purpose: build the PDF (or LaTeX) manual into `documentation/build`.
- Side effects: writes output and a temp dir. Exit 2 for environment problems, 1 for content.

### `docforge agent impact [--base REF] [--out DIR]`, `agent adr TITLE [--note TEXT]`, `agent bootstrap`

- Purpose: run the model to propose doc changes.
- Authentication: Anthropic credentials from the environment.
- Side effects: paid API calls; appends to the usage ledger; writes outputs to `documentation/build/agent` (or `--out`). Never modifies tracked docs. Requires a git repository. Exit 3 on agent failure or missing credentials.

### `docforge apply PATCH [--branch NAME]`

- Purpose: apply a reviewed patch.
- Side effects: creates a branch (default `docforge/<task>-<sha>`), stages and commits. Never pushes. Leaves the new branch checked out.

### `docforge usage [--last]`

- Purpose: show model spend from the ledger. Side effects: none.

### `docforge serve [--port N]`

- Purpose: start docforge Console on `127.0.0.1:N` (default 8765). There is deliberately no `--host` option.
- Authentication: prints a launch link `http://127.0.0.1:N/auth?t=<token>`; the token is random per launch.
- Side effects: long-running; writes `$DOCFORGE_HOME/console.json` (the repository list). Exit 2 if the `[console]` extra is not installed.

<!-- sources: src/docforge/cli.py, src/docforge/git.py, src/docforge/apply.py, src/docforge/console/app.py -->

## Console HTTP routes

For the console's own pages only. Every route requires the `Host` header to be `127.0.0.1:N` or `localhost:N` (403 otherwise). Pages require the `docforge_session` cookie set by `/auth` (401 otherwise). Every `POST /api/...` also requires the `x-docforge-token` header (403 otherwise).

| Route | Purpose |
|---|---|
| `GET /auth?t=TOKEN` | Starts a session: sets an HttpOnly, SameSite=Strict cookie, redirects to `/`. |
| `GET /`, `/repos/{id}`, `/repos/{id}/manual`, `/usage`, `/runs`, `/runs/{job}`, `/runs/{job}/review`, `/security` | Pages. |
| `POST /api/repos`, `/api/repos/{id}/remove` | Add (absolute path to a git repository) or remove a repository. |
| `POST /api/repos/{id}/build`, `GET /repos/{id}/manual.pdf` | Build the manual; serve the newest PDF inline. |
| `POST /api/replays/{name}`, `POST /api/repos/{id}/runs` | Start a replay, or a live run (`mode`, `task`, `base`, `title`, `note`). One live run at a time (409). |
| `GET /api/runs/{job}/stream` | Server-Sent Events: `line` events, then one `done` event with the summary. |
| `POST /api/runs/{job}/apply`, `/push`, `/pr` | Publish steps, only for a successful live run and only in that order (400 otherwise). See [SECURITY.md](SECURITY.md). |
| `POST /api/security/replay`, `/api/security/live` | Replay the recorded red-team run, or run `sandbox/redteam.sh`. |

<!-- sources: src/docforge/console/app.py, src/docforge/console/publish.py, src/docforge/console/runs.py -->

## Errors

Exit codes: 0 success; 1 check errors, refused/failed apply, or build content failure; 2 configuration, environment, bad base ref or non-git repository; 3 agent failure or missing credentials. Messages go to stderr prefixed `error:`. Note `check` returns 1 only for error-severity findings; warnings do not fail it unless `--strict` promotes them.

<!-- sources: src/docforge/cli.py, src/docforge/build.py, src/docforge/checks.py -->
