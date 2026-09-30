# Troubleshooting

> Practical guide. Keep historical lessons even after the bug is fixed.

## Known Problems

### Problem: Agent run fails with "budget exhausted"

- Possible symptoms: exit 3, message with per-run and monthly caps.
- Likely causes: the guard refuses a call when the remaining allowance cannot fund at least 2,048 output tokens after worst-case input cost.
- Diagnostic steps: `docforge usage`; check `[budget]` in `docforge.toml`.
- Resolution: raise `[budget.per_run_usd]` or `monthly_usd`, or wait for next month.
- Relevant logs: `trace.log`, `~/.docforge/usage.jsonl` (refusals are recorded with a note).
- Relevant components: `agent/budget.py`.
- Escalation considerations: none.

### Problem: Agent run stops without producing `docforge.patch`

- Possible symptoms: exit 3; `run.json` status `failed`.
- Likely causes (all seen in the pilot's early runs per the status note): a single response too long (`max_tokens`), the turn limit reached, a network stream dropped mid-reply. Also model refusal.
- Diagnostic steps: read `trace.log` (ends with `FAILED:`).
- Resolution: finished documents are kept in `docforge.partial.patch`; review it and apply manually if acceptable, or rerun. Dropped streams are already retried 3 times.
- Relevant components: `agent/runner.py`.

### Problem: "no Anthropic credentials"

- Likely causes: `ANTHROPIC_API_KEY` unset; or the OpenShell `anthropic` provider not attached/imported.
- Resolution: set the key on the host for direct runs; for the sandbox import `sandbox/anthropic-profile.yaml` and create the provider.

### Problem: `docforge apply` refuses the patch

- Likely causes: patch touches a path outside `README.md`, `CHANGELOG.md`, `docs/**.md`; branch already exists; patch does not apply cleanly because the docs changed since the run.
- Resolution: rerun the agent on the current tree, or pass `--branch`.

### Problem: `docforge check` reports drift or "base ref not found"

- Likely causes: a code file in an impact category changed without its docs; or a shallow CI clone.
- Resolution: update the mapped docs, or add a commit trailer `Docs-Impact: none — <reason>` (a reason is mandatory). CI uses `fetch-depth: 0` for this reason.

### Problem: PDF build fails or diagrams stay as code

- Symptoms: "missing tools", or warning "mmdc not found", or `DOCFORGE-MERMAID-FAILED`.
- Resolution: install pandoc, tectonic, mermaid-cli (`./init.sh` reports which). Mermaid needs Node >= 20 and headless Chrome. In containers set `DOCFORGE_PUPPETEER_CONFIG`. Use `--format tex` to inspect the LaTeX.
- Historical lessons (from build/sandbox comments): under OpenShell, Chromium's zygote needs a user namespace which seccomp forbids, hence `--no-zygote`; exec sessions do not inherit image ENV, so tectonic tries the (blocked) network unless `XDG_CACHE_HOME` is passed; uploads from a Windows drive (`/mnt/c`) arrive as zero bytes, so stage on the Linux filesystem.

### Problem: sandbox cannot reach the OpenShell gateway

- Likely cause (status note): Docker Desktop's network cannot reach the OpenShell gateway.
- Resolution: the status note says a separate native Docker engine was installed with `sandbox/install-native-docker.sh`; also `wsl --update` was needed. Details: uncertain — verify with developer.

### Problem: CI `docforge check` fails at install

- Likely cause: `DOCFORGE_SPEC` points at `github.com/beese54/docforge`, which did not exist at 2026-09-30.
- Resolution: publish the repository or change `DOCFORGE_SPEC`.

<!-- sources: src/docforge/agent/budget.py, src/docforge/agent/runner.py, src/docforge/apply.py, src/docforge/drift.py, src/docforge/build.py, sandbox/build.Dockerfile, sandbox/build-policy.yaml, sandbox/redteam.sh, STATUS-2026-09-30.md, .github/workflows/docforge.yml -->
