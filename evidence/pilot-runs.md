# Pilot evidence: T9–T11 on markdown-visualiser (2026-09-30)

Pilot: local clone of https://github.com/beese54/markdown-visualiser at `cc34345`. Nothing was pushed.
Branches, local only: `docforge/scaffold` (init output), then `docforge/bootstrap-24c6b4f` (T11 patch via `docforge apply`).

## T9: sandbox red-team (`sandbox/redteam.sh --agent-only`)
| ID | Control | Result |
|---|---|---|
| 5.1 | Real API key absent from the sandbox environment and filesystem (only a placeholder) | PASS |
| 5.1b | api.anthropic.com reachable, with the key swapped in at egress | PASS (HTTP 200) |
| 5.2 | Egress to example.com blocked and logged | PASS |
| 5.2b | Key not sent to a non-Anthropic host | PASS |
| 5.3 | Writes to system paths (/usr, /etc) denied | PASS |
| 5.3b | /sandbox/out writable | PASS |
| 5.4 | Build sandbox has no egress | PASS |
| 5.4b | PDF builds offline inside the OpenShell build sandbox | PASS (after three fixes, commit `3510575`) |

## T10: `agent impact --base HEAD~3` (DoD 4.5, 4.6)
- **4.5 PASS:** cost $0.0439 over 4 turns. 0 policy denials. The patch passes `git apply --check`.
- **4.6 PARTIAL:** every claim traces to the diff, but the CHANGELOG entries carry no `<!-- sources -->` comment.

## T11: `agent bootstrap` (DoD 6.x)
| # | Result |
|---|---|
| 6.1 | **PASS.** The successful run cost $1.40 (28 turns). Total T11 spend was $2.20 including three failed runs ($0.25 max_tokens, $0.54 turn limit, $0.016 dropped stream). Each failed run was a docforge bug, fixed in `4a6cd48`, `8aa3dc4` and `98ba8de`. |
| 6.2 | **PASS.** `docforge check --strict --base cc34345`: 0 errors, 0 warnings. |
| 6.3 | **PASS.** 8 ADRs (001–008), each citing code evidence. |
| 6.4 | **PASS.** 298 citations, all paths exist. The 20-claim hand audit found 19 true, 1 imprecise, 0 false (`evidence/claims-audit.md`). |
| 6.5 | **PASS.** The README went from long to 118 lines. Deep material moved to docs/ and ADR-002. |
| 6.6 | **PASS (12/13; 1 partly).** Only production deployment is marked uncertain, because the repo defines none (`evidence/final-objective.md`). |
| 6.7 | **PASS.** 62-page PDF, 0 unresolved references (`evidence/pilot-manual-428e509.pdf`). |
| 6.8 | **PASS.** https://github.com/beese54/markdown-visualiser/pull/1. The `docforge check --strict` workflow is green (docforge installed from the now-public github.com/beese54/docforge). |

## Findings for the pilot's owner (from the agent's report, confirmed)
1. `src/pipeline/sanitize.ts` exports `printSchema` ("applied server-side before the print service hands HTML to Chromium"), but nothing uses it. The server does no sanitisation.
2. The README's "mixed bullet markers" repair only normalises list spacing; mdast has no marker characters.
3. `definition_of_done.md` cites `tests/adversarial/pdf-endpoint.sh`, which does not exist. The probe is `tests/e2e/adversarial.mjs`.
