# Operations

> Running the system day to day: monitoring, alerts, routine tasks, incidents.

## Monitoring

No service to monitor. Monitor spend with `docforge usage` (per run, this month, total) and CI status of the `docforge` workflow. Agent health per run: `run.json` status and `trace.log`.

<!-- sources: src/docforge/cli.py, src/docforge/agent/runner.py, .github/workflows/docforge.yml -->

## Alerts

None configured. The monthly cap (default $10) is the only automatic guard; it refuses further calls rather than alerting.

<!-- sources: src/docforge/agent/budget.py, docforge.toml -->

## Routine Operations

- Run an impact check after significant code changes: `sandbox/run-agent.sh <repo> impact --base <ref>`, review `report.md`, then `docforge apply documentation/build/agent/docforge.patch --path <repo>`, push manually.
- First-time pass on a repository: `sandbox/run-agent.sh <repo> bootstrap` (default cap $3.00).
- Draft an ADR: `sandbox/run-agent.sh <repo> adr "Title" --note "..."`.
- Rebuild sandbox images after a version bump: `sandbox/build-images.sh`.
- Re-verify sandbox controls: `sandbox/redteam.sh`.
- Build the manual: `docforge build` or the CI `manual` job.

<!-- sources: sandbox/run-agent.sh, sandbox/build-images.sh, sandbox/redteam.sh, src/docforge/cli.py -->

## Incident Response

- Suspected key leak: rotate the Anthropic key at the provider and update the OpenShell provider (uncertain — verify with developer for commands). Check `sandbox/redteam.sh` control 5.1.
- Unexpected spend: `docforge usage`; inspect `~/.docforge/usage.jsonl` (`note` field marks refusals and worst-case charges).
- Agent attempted disallowed writes or reads: see `policy.log`; the denials are already enforced, but review the patch carefully.
- A bad patch was applied: it is on its own branch; delete the branch.
- Other symptoms: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

<!-- sources: sandbox/redteam.sh, src/docforge/agent/budget.py, src/docforge/agent/policy.py, src/docforge/apply.py -->
