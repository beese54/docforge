# Security

> Security architecture, trust boundaries and who is responsible for what.

## Trust Boundaries

1. **Model output is untrusted.** It can only act through `ToolLayer`; writes are staged, not applied.
2. **Agent patch is untrusted at apply time.** `docforge apply` re-validates every path.
3. **Sandbox vs host.** The agent runs on a copy of the repository in an OpenShell sandbox; only `/sandbox/out` returns.
4. **Repository content is untrusted input to the model** (prompt injection via file contents is possible; mitigated only by the write allowlist and human review).

<!-- sources: src/docforge/agent/policy.py, src/docforge/apply.py, sandbox/agent-policy.yaml -->

## Authentication

No user authentication. Outbound: Anthropic API key via the SDK (`ANTHROPIC_API_KEY`). In the sandbox the key is a placeholder replaced by OpenShell at egress, only for `api.anthropic.com`, only for listed binaries (curl, python3).

<!-- sources: src/docforge/cli.py, sandbox/anthropic-profile.yaml -->

## Authorisation

Write allowlist `README.md`, `CHANGELOG.md`, `docs/**`, and only `.md` files; not configurable ([ADR-003](adr/003-openshell-sandboxes.md) and [ADR-001](adr/001-human-reviewed-patches-only.md)). Reads are confined to the repository root: absolute paths, `..`, backslashes, NUL and symlink escapes are denied.

<!-- sources: src/docforge/config.py, src/docforge/agent/policy.py, src/docforge/apply.py -->

## Secrets Management

Secret-like files are unreadable by the agent and excluded from listings, grep and diff: `.env*`, `*.pem`, `*.key`, `id_rsa*`, `*.p12`, `.git/**`, `.npmrc`, `.pypirc`. The real API key is not baked into images or put in the sandbox. Note the `.git/**` exclusion covers file reads, while the sandbox upload does include `.git` so the agent can diff.

<!-- sources: src/docforge/agent/policy.py, sandbox/agent.Dockerfile, sandbox/run-agent.sh -->

## Session Handling

Not applicable (no sessions).

<!-- sources: src/docforge/cli.py -->

## API Security

No inbound API. The CLI's outbound call goes to the Anthropic API over HTTPS.

<!-- sources: src/docforge/agent/runner.py -->

## Network Exposure

Agent sandbox: `network_policies` is empty; the only egress comes from the `anthropic` provider profile (api.anthropic.com:443). Build sandbox: no egress and no provider. No listening ports.

<!-- sources: sandbox/agent-policy.yaml, sandbox/build-policy.yaml, sandbox/anthropic-profile.yaml -->

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
