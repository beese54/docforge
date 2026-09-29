# OpenShell Autonomous Agent — Feasibility & Plan

Status: PLAN — awaiting approval before any build (no production code yet).
Protocol: sonnet5-protocols Pattern AX (Secure Agent Workspace). Once a use case is picked, chain Pattern AF (agent loop).

## Verdict
Yes, this is feasible. OpenShell is built for this job ("safe, private runtime for autonomous agents").
- Each agent runs in its own sandbox. Filesystem access is limited by Landlock, syscalls by seccomp, and the network is in its own namespace.
- All egress goes through a policy proxy that denies by default.
- The API key lives in a gateway "provider". The agent calls `inference.local` and never sees the real key.
- Policy is YAML. Filesystem and process rules are fixed when the sandbox is created. Network and inference rules can be reloaded while it runs.

Caveats:
1. Windows is supported only through WSL2, and that path is marked **experimental**. This machine has Ubuntu-24.04 on WSL2 and Docker Desktop 29.8.1, so it can start.
2. The project is young (0.1.x) and the CLI syntax has changed between versions. Blog posts show conflicting commands. Take the syntax from `openshell --help` on the installed version, not from blogs.
3. It is terminal-only, with no computer-use/GUI agents.
4. "Continuous" means a sandbox that runs for a long time. A laptop that sleeps is not a real 24/7 host. For true always-on, plan to move to a Linux VM later.
5. OpenShell contains the agent. It does not make the agent's decisions correct. You still need a human approval gate for irreversible actions and a budget cap on the key.

## Architecture (target)
```
Windows 11 host
 └─ WSL2 Ubuntu-24.04
     ├─ Docker engine
     └─ OpenShell gateway (control plane: policy, providers, audit)
         ├─ Provider: model API key (stored in gateway, never in sandbox)
         └─ Sandbox "agent-01"
             ├─ agent loop (Claude Code headless / custom SDK loop)
             ├─ /sandbox/work  (only writable area)
             ├─ egress: inference.local + explicit allowlist only
             └─ outbox/  ← proposed irreversible actions wait here for human approval
```

## Phases (check in after each)
### Phase 0 — Decide the use case (you)
- [ ] Choose a use case (shortlist below). It sets the tools, egress allowlist, and blast radius.
- [ ] Choose a provider and model, and set a **hard spend limit** on the key in the provider console.

### Phase 1 — Timeboxed spike: install & smoke test (~1–2 h)
- [ ] Start WSL2 Ubuntu and enable Docker Desktop WSL integration
- [ ] Install inside WSL: `curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh`
- [ ] Record the version, save `openshell --help` output to `evidence/cli-help.txt`, and disable telemetry
- [ ] `openshell sandbox create --name demo`, then check the shell works and default egress is denied
- [ ] Register the API key as a provider (exact command from `--help`), then launch `claude` inside a sandbox
- [ ] Exit criterion: the agent answers a prompt using the model, and `env`/`grep` inside the sandbox does not find the key

### Phase 2 — Policy & controls (Pattern AX: every control has a scripted attack that must be blocked and logged)
- [ ] Write `policy/agent-01.yaml` with least privilege for the chosen use case
- [ ] Controls and the attack that tests each one:
  | Control | Attack | Pass = |
  |---|---|---|
  | Isolation | read `/mnt/c/...` host files, write outside `/sandbox/work` | denied + logged |
  | Default-deny egress | `curl https://example.com`, DNS exfil attempt | blocked + logged |
  | Key never in sandbox | grep env/fs/proc for key prefix | no match |
  | Process limits | run a binary that is not on the allowlist | denied |
  | Spend cap | burst requests past the quota | provider-side 429/limit hit |
  | Human gate | agent tries an irreversible action | only written to outbox; not executed |
  | Audit | all of the above | appears in `openshell logs` |
- [ ] Put them all in `redteam.sh`, which prints a PASS/FAIL scorecard

### Phase 3 — Continuous operation & monitoring
- [ ] Agent loop runs on a schedule (cron inside WSL, or a long-lived loop with a sleep and budget per cycle)
- [ ] Monitoring: `openshell term` for a live view, plus `openshell logs <sb> --tail` saved to a file
- [ ] Heartbeat and alerts: if a run is missed, a policy is denied, or spend spikes, notify you (email/Telegram, via an allowlisted endpoint)
- [ ] Kill switch: one command stops the sandbox and revokes the provider

### Phase 4 — Harden / relocate (optional)
- [ ] Move to an always-on Linux VM (home server or cloud), using the same policy files
- [ ] Remote gateway plus `openshell term` from the laptop

## Use-case shortlist (low → higher blast radius)
1. **Research/news watcher.** Reads an allowlist of sites/RSS, writes a daily digest. Read-only web, no secrets besides the model key. Best first pick.
2. **Repo janitor.** Clones your GitHub repos read-only, runs tests and linters, and opens *draft* PRs with a fine-grained token scoped to specific repos.
3. **Log/infra sentinel.** Tails logs you push into `/sandbox/work` and flags anomalies. It needs no internet except the model.
4. **Engineering validation runner.** Batch-checks FEA/CAD script outputs, for example your Fusion 360 `fea_validation` work, inside the sandbox. It needs no network except the model.
5. **Inbox/calendar triage.** Useful, but it touches personal data and can send messages. Do it last, with the human gate mandatory.

## Review
(fill in after execution)

## Session log — 2026-09-29
- docforge spec approved (specification.json, definition_of_done.md, progress_tracking.json).
- WSL setup done: allti added to `docker` group; OpenShell 0.1.2 installed (/usr/bin/openshell).
- Gateway fix: `OPENSHELL_COMPUTE_DRIVER=docker` in ~/.config/openshell/gateway.env + `wsl --terminate Ubuntu-24.04` (stale group membership) → gateway running, mTLS connected.
- BLOCKED: Anthropic Console was down, so there is no API key yet. Resume at: create key → `read -rs` → `openshell provider create --name anthropic --type anthropic --credential ANTHROPIC_API_KEY` → `unset`.
- Not started: T0–T8 (need no key or credit).
- 2026-09-29 (later): T0–T8 built and committed (133 tests passing, no API spend). The WSL toolchain now has pandoc 3.1.3, tectonic 0.17, Node 22 (in ~/.local), mermaid-cli 11 + chrome-headless-shell, uv.
- Key setup gotcha: OpenShell 0.1.2 has NO provider profiles. Import sandbox/anthropic-profile.yaml before `provider create`.
- Next: T9 (sandbox image + policy + redteam.sh) once the provider exists; T10/T11 spend credit and need approval first.
- 2026-09-30 00:30: T9 PARTIAL / BLOCKED. OpenShell sandboxes cannot start on this machine: the WSL kernel is 5.15.167 (WSL 2.4.13),
  and OpenShell 0.1.2 requires Landlock ABI v3 (kernel >= 6.2). Docker driver: "partially incompatible access-rights Refer|Truncate".
  VM driver (KVM works) boots but its supervisor fails "read /proc/self/status: Permission denied". Gateway reverted to docker.
  Done without sandboxes: agent + build images (build image verified: pilot PDF builds with --network none, read-only root,
  uid 1000, Mermaid included), policies, run-agent.sh, redteam.sh (syntax-checked; policies unvalidated — 0.1.2 has no `policy prove`).
  Likely fix (needs user): `wsl --update` (newer WSL ships a 6.6 kernel), then `wsl --shutdown`, then sandbox/redteam.sh.
  T10/T11 NOT run: the key lives only in the OpenShell gateway, so no sandbox = no model access. $0 spent.
- 2026-09-30: user ran `wsl --update` -> WSL 3.0.1, kernel 6.18.40. The Landlock blocker is FIXED (sandbox gets past the probe).
  NEW BLOCKER: OpenShell's Docker driver runs the supervisor on the "host network" and dials the gateway at 127.0.0.1:17670,
  but Docker Desktop's host network is its own VM (192.168.65.x), so the supervisor can't reach the gateway ("Startup configuration fetch failed").
  VM driver: still fails in-guest ("read /proc/self/status: Permission denied"). Podman: OpenShell needs 5.x, Ubuntu 24.04 has 4.9.
  Proposed fix (needs user approval, blocked by permission policy): a native Docker engine inside Ubuntu as a separate systemd
  service (docker-openshell, own socket/data-root/bridge), with OpenShell's docker socket_path pointed at it. Gateway left on docker.
- 2026-09-30: user installed native Docker (sandbox/install-native-docker.sh); OpenShell now uses /run/docker-openshell.sock
  via ~/.config/openshell/gateway.toml. Red-team agent controls all PASS. T10 done ($0.04). T11 bootstrap done on 4th
  attempt ($1.40; T11 total $2.20; total spend $2.25). Evidence: evidence/pilot-runs.md. Pilot branch (local only):
  /tmp/pilot-live docforge/bootstrap-24c6b4f. Remaining: 6.4 full audit, 6.6 checklist, 6.8 user PR + publish docforge, T12.
