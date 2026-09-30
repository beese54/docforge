# ADR-003: Run the agent and the PDF build in OpenShell sandboxes

## Status

Accepted

## Context

The agent reads a repository and talks to an external API; the PDF build runs pandoc, LaTeX and headless Chromium over repository content. Both should have minimal privileges, and the API key should not be exposed.

## Options Considered

- Run on the host.
- Plain Docker. (The build was verified offline this way per `build-policy.yaml`.)
- OpenShell sandboxes with policy files (chosen).

## Decision

- Agent sandbox: image `docforge-agent`, `agent-policy.yaml` (read-only system paths, writable `/sandbox`, `/tmp`; empty network policy), plus the `anthropic` provider profile granting api.anthropic.com:443 to listed binaries, with the real key injected at egress.
- Build sandbox: image `docforge-build` with all downloads baked in at image build time, `build-policy.yaml` with no network at all.
- The repository is uploaded as a copy; only `/sandbox/out` is returned.
- Controls are verified by `sandbox/redteam.sh`.

## Rationale

From the policy file comments: writes in the sandbox cannot reach the host repo; the key never enters the sandbox; the build needs no egress. Why OpenShell over alternatives: uncertain — verify with developer.

## Consequences

- Requires OpenShell and a compatible Docker engine (status note: Docker Desktop's network could not reach the gateway).
- Chromium must run with `--no-zygote`; exec sessions do not inherit image ENV.
- Landlock is `best_effort`.

## Related Components

`sandbox/`, [SECURITY.md](../SECURITY.md), [DEPLOYMENT.md](../DEPLOYMENT.md)
