# How It Works

> End-to-end workflows.

## Workflows

### Workflow: Scaffold (`docforge init`)

1. Trigger: engineer runs `docforge init [--path .]`.
2. Received by: `cli.init` then `init.scaffold`.
3. Processing: builds a plan of skeleton docs (from `doctypes.py`), CHANGELOG, ADR template, manual defaults, CI workflow and `docforge.toml`. The impact map is guessed by matching candidate globs against files that exist.
4. Services called: `git ls-files` (falls back to a directory walk).
5. Data stored: only missing files are created (opened with mode `x`); `documentation/build/` is appended to `.gitignore`.
6. Asynchronous work: none.
7. Result: list of created/existing files.
8. What can fail: nothing is overwritten; a guessed impact map may be wrong and must be reviewed.

<!-- sources: src/docforge/init.py, src/docforge/cli.py -->

### Workflow: Check (`docforge check`)

1. Trigger: engineer or CI (`docforge check --strict --base <ref>`).
2. Received by: `cli.check`, `checks.run` plus the drift check.
3. Processing: required files exist; required H2 sections; internal links and anchors (case-exact); ADR naming, numbering (no gaps), title and status; count of "uncertain" markers (limit `[uncertain] max_markers`); drift. `--strict` turns soft rules and drift in `adr_worthy` categories into errors.
4. Services called: git (`log`, `merge-base`, `diff`).
5. Data stored: none.
6. Asynchronous work: none.
7. Result: findings as text or JSON; exit 1 if any error.
8. What can fail: base ref missing (shallow clone) is an error; no base ref or not a repo is only informational; invalid `docforge.toml` exits 2.

Drift: for each impact rule, if a non-overridden changed file matches its globs and none of its docs changed in the same range (or uncommitted), a finding is raised.

<!-- sources: src/docforge/checks.py, src/docforge/drift.py, src/docforge/git.py, src/docforge/cli.py -->

### Workflow: Agent run (`docforge agent impact|adr|bootstrap`)

1. Trigger: engineer, normally via `sandbox/run-agent.sh <repo> <task>`.
2. Received by: `cli._run_agent`, which loads config, checks git and credentials and creates a `BudgetGuard` (per-run cap by command, monthly cap).
3. Processing: loop in `agent/runner.py`. Each turn counts input tokens, sizes `max_tokens` to the remaining budget, streams a response, records cost, executes tool calls through `ToolLayer`. Ends when the model calls `finish`, or when it stops without tools (its text becomes the report). Turn limits: impact 40, adr 20, bootstrap 120.
4. Services called: Anthropic API (model `claude-sonnet-5-5`, adaptive thinking, effort medium).
5. Data stored: `usage.jsonl` per call; in the output dir `docforge.patch`, `report.md`, `policy.log`, `trace.log`, `run.json` (default `documentation/build/agent`).
6. Asynchronous work: none; streaming is synchronous.
7. Result: a patch and report for human review. The repository is untouched.
8. What can fail: budget exhausted, model refusal, `max_tokens` hit, turn limit, API or connection errors, missing credentials (exit 3). Denied tool calls are logged and returned to the model.

<!-- sources: src/docforge/cli.py, src/docforge/agent/runner.py, src/docforge/agent/budget.py, src/docforge/agent/policy.py, sandbox/run-agent.sh -->

### Workflow: Sandboxed agent run (`sandbox/run-agent.sh`)

1. Trigger: engineer on the host.
2. Processing: copies the usage ledger; creates an OpenShell sandbox from `docforge-agent:<version>` with `agent-policy.yaml` and the `anthropic` provider; uploads the repository (working tree plus `.git`) as a tar; runs `docforge agent ... --out /sandbox/out`; downloads outputs and the ledger back to `<repo>/documentation/build/agent`; deletes the sandbox on exit.
3. Failure modes: OpenShell/Docker problems; the script propagates the agent's exit status.

<!-- sources: sandbox/run-agent.sh, sandbox/agent-policy.yaml -->

### Workflow: Apply (`docforge apply <patch>`)

1. Trigger: engineer after reviewing `report.md` and the patch.
2. Processing: extracts all paths in the patch; refuses anything outside `README.md`, `CHANGELOG.md`, `docs/**` `.md`; names the branch `docforge/<task>-<sha>` from `run.json` (or `--branch`); `git apply --check --index`; creates the branch, applies, commits.
3. Result: commit on a new branch. Never pushes.
4. What can fail: empty patch, disallowed path, existing branch, patch not applying cleanly (exit 1).

<!-- sources: src/docforge/apply.py, src/docforge/cli.py -->

### Workflow: Build manual (`docforge build`)

1. Trigger: engineer or CI job `manual` (workflow_dispatch or tags).
2. Processing: requires pandoc and tectonic (tectonic not needed for `--format tex`); expands `[manual] chapters` (globs sorted, `000-*` skipped); fills version (`git describe --tags --always --dirty`), date and SHA into the LaTeX header; runs pandoc with the Lua filter.
3. Result: `documentation/build/<name>-manual-<version>.pdf`.
4. What can fail: missing tools (exit 2), no chapters (exit 2), pandoc failure (exit 1), Mermaid render failure (warning; error with `--strict`). Without `mmdc`, diagrams remain code blocks.

<!-- sources: src/docforge/build.py, src/docforge/templates/docforge.lua, .github/workflows/docforge.yml -->

### Workflow: Usage report (`docforge usage`)

Reads the ledger and prints spend per run, this month and total.

<!-- sources: src/docforge/cli.py, src/docforge/agent/budget.py -->

### Workflow: Console run and publish (`docforge serve`)

1. Trigger: the developer opens the printed launch link. `/auth` checks the token, sets the session cookie and shows the Repos screen.
2. Received by: `console/app.py` (FastAPI) on 127.0.0.1, after the Host check.
3. Processing: Repos and repo detail call `health.compute` (the same `checks.run` + drift as the CLI) and `views.coverage`/`views.adrs`.
4. Services called: a **replay** thread plays `console/replays/<name>/trace.log` at a readable pace. A **live** run starts `sandbox/run-agent.sh <repo> <task>` and reads its output line by line; with `DOCFORGE_PROGRESS=1` the agent prints each trace line as it happens.
5. Data stored: runs are held in memory for the session. Live outputs land in `<repo>/documentation/build/agent` exactly as with the CLI. The repository list is in `$DOCFORGE_HOME/console.json`.
6. Asynchronous work: runs execute in background threads; the browser follows them over Server-Sent Events (`/api/runs/<job>/stream`).
7. Result: the Review screen shows the report, the patch as a diff and any policy denials. For a successful live run, Apply → Push → Open PR appear one at a time (see [SECURITY.md](SECURITY.md#api-security) for the guards).
8. What can fail: a second live run while one is running (409); a failed run (no patch, maybe a partial one); push without credentials (fails fast, never prompts); `gh` missing or not logged in.

<!-- sources: src/docforge/console/app.py, src/docforge/console/runs.py, src/docforge/console/publish.py, src/docforge/agent/runner.py, sandbox/run-agent.sh -->
