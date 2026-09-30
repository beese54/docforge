# API

> Behaviour, assumptions and side effects that a generated API spec does not capture.

## Overview

The interface is the `docforge` CLI (Typer). There is no HTTP API. `--path` (repository root, default `.`) applies to all commands except `usage`. `docforge --version` prints the version.

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

<!-- sources: src/docforge/cli.py, src/docforge/git.py, src/docforge/apply.py -->

## Errors

Exit codes: 0 success; 1 check errors, refused/failed apply, or build content failure; 2 configuration, environment, bad base ref or non-git repository; 3 agent failure or missing credentials. Messages go to stderr prefixed `error:`. Note `check` returns 1 only for error-severity findings; warnings do not fail it unless `--strict` promotes them.

<!-- sources: src/docforge/cli.py, src/docforge/build.py, src/docforge/checks.py -->
