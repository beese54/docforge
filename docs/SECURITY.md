# Security

> Security architecture, trust boundaries and who is responsible for what.

## Trust Boundaries

1. **Model output is untrusted.** It can only act through `ToolLayer`; writes are staged, not applied.
2. **Agent patch is untrusted at apply time.** `docforge apply` re-validates every path.
3. **Sandbox vs host.** The agent runs on a copy of the repository in an OpenShell sandbox; only `/sandbox/out` returns.
4. **Repository content is untrusted input to the model** (prompt injection via file contents is possible; mitigated only by the write allowlist and human review).

<!-- sources: src/docforge/agent/policy.py, src/docforge/apply.py, sandbox/agent-policy.yaml -->

## Authentication

No user authentication for the CLI. Outbound: Anthropic API key via the SDK (`ANTHROPIC_API_KEY`). In the sandbox the key is a placeholder replaced by OpenShell at egress, only for `api.anthropic.com`, only for listed binaries (curl, python3).

**Console (`docforge serve`).** A random launch token is generated per start and printed as a link. Opening it sets the `docforge_session` cookie (HttpOnly, SameSite=Strict); every page needs the cookie. The console never reads or stores the Anthropic key or any GitHub token: live runs go through `run-agent.sh` and the OpenShell provider, and publishing uses the developer's existing git credential helper and `gh` login.

<!-- sources: src/docforge/cli.py, sandbox/anthropic-profile.yaml, src/docforge/console/app.py, src/docforge/console/publish.py -->

## Authorisation

Write allowlist `README.md`, `CHANGELOG.md`, `docs/**`, and only `.md` files; not configurable ([ADR-003](adr/003-openshell-sandboxes.md) and [ADR-001](adr/001-human-reviewed-patches-only.md)). Reads are confined to the repository root: absolute paths, `..`, backslashes, NUL and symlink escapes are denied.

<!-- sources: src/docforge/config.py, src/docforge/agent/policy.py, src/docforge/apply.py -->

## Secrets Management

Secret-like files are unreadable by the agent and excluded from listings, grep and diff: `.env*`, `*.pem`, `*.key`, `id_rsa*`, `*.p12`, `.git/**`, `.npmrc`, `.pypirc`. The real API key is not baked into images or put in the sandbox. Note the `.git/**` exclusion covers file reads, while the sandbox upload does include `.git` so the agent can diff.

<!-- sources: src/docforge/agent/policy.py, sandbox/agent.Dockerfile, sandbox/run-agent.sh -->

## Session Handling

The CLI has no sessions. The console has one session per launch: the token changes every time `docforge serve` starts, so old links and cookies stop working. The session lives only in the server's memory.

<!-- sources: src/docforge/cli.py, src/docforge/console/app.py -->

## API Security

The CLI has no inbound API; its outbound call goes to the Anthropic API over HTTPS.

The console's local HTTP routes assume a hostile website may be open in the same browser:

- **DNS rebinding:** every request whose `Host` header is not `127.0.0.1:<port>` or `localhost:<port>` is refused (403).
- **Cross-site requests (CSRF):** state-changing `POST /api/...` routes require the launch token in the `x-docforge-token` header as well as the cookie. Only pages served by the console can read the token (from a meta tag), and the SameSite=Strict cookie is not sent cross-site.
- **Publishing guards (`console/publish.py`):** Apply is exactly `docforge apply`. Push sends only a `docforge/*` branch that this console applied (the name is held server-side, never taken from the request), with an explicit refspec to the existing `origin`, never `--force`, never `main`/`master`, and names with `..`, empty segments or `.lock` are refused. Open PR works only for a branch this console pushed. Each step needs a browser confirm, and the confirm screen lists remote, branch, commits and files.
- **Replays** can never be applied or pushed, and never call the model.
- Agent-written reports are rendered with an escaping Markdown renderer, so a report cannot inject HTML.

<!-- sources: src/docforge/agent/runner.py, src/docforge/console/app.py, src/docforge/console/publish.py, src/docforge/console/views.py, tests/test_console.py, tests/test_console_publish.py -->

## Network Exposure

Agent sandbox: `network_policies` is empty; the only egress comes from the `anthropic` provider profile (api.anthropic.com:443). Build sandbox: no egress and no provider. The console listens on `127.0.0.1` only, and has no option to bind anything else. The CLI listens on no ports.

<!-- sources: sandbox/agent-policy.yaml, sandbox/build-policy.yaml, sandbox/anthropic-profile.yaml, src/docforge/cli.py -->

## Input Validation

- Config: strict key and type validation.
- Tool arguments: strict JSON schemas (`additionalProperties: false`), size limits (200,000-byte reads, 150,000-char diff, 200 grep matches, 2,000 listed files), binary files refused.
- Patch paths: diff headers, `---/+++` and rename/copy lines are all parsed for allowlist checking.

<!-- sources: src/docforge/config.py, src/docforge/agent/policy.py, src/docforge/apply.py -->

## Dependency Security

No scanning is configured in the repository (uncertain — verify with developer). Versions are locked in `uv.lock`. `anthropic` is unpinned in `pyproject.toml`. See [DEPENDENCIES.md](DEPENDENCIES.md).

<!-- sources: pyproject.toml, .github/workflows/docforge.yml -->

## Logging and Audit

Each denial is logged with timestamp, tool, path and reason to `policy.log`; every model call is appended to the usage ledger. Neither is tamper-protected.

<!-- sources: src/docforge/agent/policy.py, src/docforge/agent/budget.py -->

## Sensitive Data

Repository contents that the agent reads (excluding secret patterns) are sent to the Anthropic API. Do not run the agent on repositories whose non-secret files may not leave your environment. Secrets under other filenames would not be filtered (uncertain — verify with developer whether additional patterns are needed).

<!-- sources: src/docforge/agent/policy.py -->

## Rate Limiting

None on requests. Spend is capped per run and per month by construction ([ADR-002](adr/002-budget-guard-and-manual-agent-loop.md)), plus turn limits.

<!-- sources: src/docforge/agent/budget.py, src/docforge/agent/runner.py -->

## Encryption and TLS

Outbound TLS is handled by the Anthropic SDK; the CI installer uses `curl --proto '=https' --tlsv1.2`. The usage ledger is stored unencrypted.

<!-- sources: .github/workflows/docforge.yml, src/docforge/agent/budget.py -->

## Security Assumptions

- OpenShell enforces the filesystem, landlock and egress policies (landlock `best_effort`, so weaker kernels may enforce less).
- The host user reviews patches before applying.
- `sandbox/redteam.sh` is the evidence for controls 5.1–5.4b; per the 2026-09-30 status note, the build-sandbox checks still needed a rerun.

<!-- sources: sandbox/agent-policy.yaml, sandbox/redteam.sh, STATUS-2026-09-30.md -->

## Responsibilities

- Developer running the agent: review `report.md` and the patch, keep the API key on the host, keep spend caps sensible.
- Maintainer: keep policy files, `redteam.sh` and this document in step (strict impact rule `security`).
- Pilot finding: a downstream project had unused sanitising code; docforge itself is not affected.

<!-- sources: docforge.toml, STATUS-2026-09-30.md -->
