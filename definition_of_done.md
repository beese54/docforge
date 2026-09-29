# Definition of Done: docforge MVP

Each criterion names the command or check that proves it. If running that command doesn't show the criterion is met, it is **not done**.
Criteria marked 💲 spend real API credit. They run only after you approve, and each shows its cost from `docforge usage`.

## P0: Environment
| # | Criterion | Verified by |
|---|---|---|
| 0.1 | The prerequisites are present in WSL: python 3.12, uv, git, pandoc ≥3, tectonic, mmdc, docker, openshell | `./init.sh` exits 0 |
| 0.2 | The package installs and the CLI runs | `uv run docforge --help` |
| 0.3 | Lint, types and unit tests are clean | `uv run ruff check && uv run mypy src && uv run pytest` |

## P1: init
| # | Criterion | Verified by |
|---|---|---|
| 1.1 | In an empty git repo, init creates every file listed in the spec | `pytest -k init_creates` (asserts the file list) |
| 1.2 | It is idempotent: a second run changes nothing | `pytest -k init_idempotent` (`git status --porcelain` is empty after the 2nd run) |
| 1.3 | It never overwrites existing files | `pytest -k init_no_overwrite` (the checksum of an existing README is unchanged) |
| 1.4 | The generated repo passes `check` without `--strict` | `pytest -k init_then_check` |

## P2: check
| # | Criterion | Verified by |
|---|---|---|
| 2.1 | A missing required doc gives an error and exit code 1 | `pytest -k structure` |
| 2.2 | A broken relative link or #anchor gives an error | `pytest -k links` |
| 2.3 | A bad ADR (number gap, invalid Status, Superseded with no successor) gives an error | `pytest -k adr` |
| 2.4 | Drift: changing `package.json` without touching `DEPENDENCIES.md` gives a warning, and an error under `--strict` | `pytest -k drift` |
| 2.5 | The `Docs-Impact: none — reason` trailer suppresses drift, and an empty reason does not | `pytest -k drift_override` |
| 2.6 | `--format json` output validates against the finding schema | `pytest -k json_schema` |
| 2.7 | check never calls the network | `pytest -k no_network` (sockets are blocked during the test) |

## P3: build
| # | Criterion | Verified by |
|---|---|---|
| 3.1 | The fixture docs build into a PDF | `docforge build` → the file exists and `pdfinfo` reports ≥ 1 page |
| 3.2 | The PDF has a table of contents, numbered sections, and a version equal to `git describe` | `pdftotext` output contains "Contents", "1 Introduction" and the exact describe string |
| 3.3 | Mermaid diagrams appear as numbered figures | `pdftotext` output contains "Figure 1", and `pdfimages -list` or vector check ≥ 1 |
| 3.4 | Cross-references resolve (no "??" in the output) | `pdftotext … \| grep -c '??'` = 0 |
| 3.5 | The build succeeds with networking disabled | Build runs in the OpenShell build sandbox with no egress (P5.4) |

## P4: agent (no-spend tests first)
| # | Criterion | Verified by |
|---|---|---|
| 4.1 | `write_doc` rejects any path outside README/CHANGELOG/docs/** and logs it | `pytest -k pep_allowlist` (mocked model) |
| 4.2 | The budget guard refuses a call that would exceed the per-run cap and exits 3 | `pytest -k budget_guard` (mocked count_tokens) |
| 4.3 | An API error or timeout exits 3 and writes no partial patch | `pytest -k api_failure` |
| 4.4 | `apply` refuses a patch that touches non-doc paths | `pytest -k apply_refuses` |
| 4.5 💲 | One live `agent impact` run on the pilot costs ≤ $0.50 | `docforge usage --last` |
| 4.6 💲 | The live output follows the honesty rules: every written section has a `sources:` comment, and each cited path exists | `docforge check --verify-sources` (a script that resolves each cited path) |

## P5: OpenShell containment (Pattern AX: each attack must be blocked and logged)
| # | Criterion | Verified by |
|---|---|---|
| 5.1 | The real API key is not visible inside the agent sandbox (only the placeholder) | `redteam.sh`: grep of env, /proc and the filesystem for the key prefix finds nothing |
| 5.2 | Egress to anything except api.anthropic.com is blocked | `redteam.sh`: `curl https://example.com` fails, and the denial shows up in `openshell logs` |
| 5.3 | Writes outside /sandbox/out are denied | `redteam.sh`: writing to /sandbox/repo/src fails and is logged |
| 5.4 | The build sandbox has no egress and still builds the PDF | `redteam.sh`: the curl fails and `docforge build` succeeds |
| 5.5 | A single scorecard reports all of the above | `redteam.sh` prints PASS on every row and exits 0 |

## P6: Pilot acceptance (markdown-visualiser)
| # | Criterion | Verified by |
|---|---|---|
| 6.1 💲 | `agent bootstrap` costs ≤ $3.00 | `docforge usage --last` |
| 6.2 | On the pilot branch, `docforge check --strict` passes | the command exits 0 |
| 6.3 | ≥ 5 ADRs, each tied to a decision visible in code, with cited files | manual review against `pilot_observations.adr_candidates_visible_in_code` |
| 6.4 | No invented claims: a random sample of 20 claims each traces to a cited file or is marked uncertain | a review table of 20 claims saved in `evidence/claims-audit.md` |
| 6.5 | The README content now lives in docs/ with no duplicate copies, and the README links to it | manual diff review; the README is ≤ ~120 lines |
| 6.6 | Each of the 13 "Final Objective" questions is answered by a doc and section | a checklist in `evidence/final-objective.md` |
| 6.7 | The PDF manual for the pilot builds | the `documentation/build/*.pdf` file exists and meets 3.2–3.4 |
| 6.8 | The docforge GitHub workflow is green on the pilot PR | the Actions run is green *(the PR is opened by you, not by the agent)* |

## P7: Dogfood + budget
| # | Criterion | Verified by |
|---|---|---|
| 7.1 | docforge's own repo passes `check --strict`, with ADR-001 (Pandoc vs Quarto) | `docforge check --strict` in its own repo |
| 7.2 | Total live spend for the MVP is ≤ $10.00 | `docforge usage --total` |
