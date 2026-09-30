# Bootstrap report

## Summary
All 14 documents in the set were filled from a selective read of the repository (source, sandbox files, CI, config, status note). I also added 7 ADRs and a CHANGELOG entry. Nothing was applied. All writes are staged for review.

## Documents changed
- **README.md**: rewritten from a 5-line stub into the 8 required sections. **This is a hand-written file.** No deep material existed to move into docs/. The old pointer to `specification.json` and `definition_of_done.md` is kept, but I did not read those two files.
- **docs/ARCHITECTURE, DESIGN, HOW_IT_WORKS, DEPLOYMENT, MAINTENANCE, TROUBLESHOOTING, SECURITY, TESTING, DATA_MODEL, API, DEPENDENCIES, OPERATIONS**: replaced stubs.
- **docs/adr/001–007**, all Accepted:
  - 001 human-reviewed patches and the path allowlist
  - 002 manual agent loop with a budget guard
  - 003 OpenShell sandboxes
  - 004 deterministic checks only in CI
  - 005 impact-map drift detection
  - 006 pandoc/tectonic manual pipeline
  - 007 doctypes as the single source of truth
- **CHANGELOG.md**: entries under [Unreleased].

## Impact checklist
Architecture, Design, APIs, Deployment, Security, Dependencies, Testing, Operations, Maintenance, Troubleshooting and Architecture decisions: all yes, since every doc was empty. Data model: yes, but small (no database; ledger and config only).

## Discrepancies
- `docforge.toml` and the CI workflow both point to `github.com/beese54/docforge`. The 2026-09-30 status note says that repo did not exist yet. I marked this as uncertain and as a known problem.
- `sandbox/agent.Dockerfile` and `build.Dockerfile` say to build with the version `0.1.0`. The scripts derive the tag from `pyproject.toml`, so the two can drift.
- `runner.py` imports `httpx2`, which is not a direct dependency in `pyproject.toml`. I did not read `uv.lock`, so I could not tell whether it comes in through `anthropic`.
- The security and impact-map wording claims a `.git/**` read block, but the sandbox upload deliberately includes `.git`. I documented both.

## Uncertain items needing the developer
- What each test file actually covers. I read only `conftest.py` and `test_smoke.py`.
- Rotation and cleanup commands for the OpenShell provider and for leftover sandboxes.
- What `sandbox/install-native-docker.sh` changes on the host.
- Whether a release, distribution or rollback process exists.
- Whether dependency scanning exists.
- Why OpenShell and tectonic were chosen over the alternatives (the ADRs mark these as uncertain).
- The contents of `specification.json`, `definition_of_done.md`, `evidence/`, `markdown.py`, `findings.py`, `globs.py` and `uv.lock`. I did not read them.
- Whether the `docs/SECURITY.md` "Responsibilities" bullet about the pilot finding should stay. It is taken from the status note and may be noise.

## ADRs proposed
ADR-001 to ADR-007 above, all Accepted, each citing code comments as evidence.


---
Run `07f9d223ba2d` (bootstrap): 22 model turn(s), cost $0.7344. Files in patch: CHANGELOG.md, README.md, docs/API.md, docs/ARCHITECTURE.md, docs/DATA_MODEL.md, docs/DEPENDENCIES.md, docs/DEPLOYMENT.md, docs/DESIGN.md, docs/HOW_IT_WORKS.md, docs/MAINTENANCE.md, docs/OPERATIONS.md, docs/SECURITY.md, docs/TESTING.md, docs/TROUBLESHOOTING.md, docs/adr/001-human-reviewed-patches-only.md, docs/adr/002-budget-guard-and-manual-agent-loop.md, docs/adr/003-openshell-sandboxes.md, docs/adr/004-deterministic-checks-in-ci.md, docs/adr/005-impact-map-drift-detection.md, docs/adr/006-pandoc-tectonic-manual-pipeline.md, docs/adr/007-doctypes-single-source-of-truth.md. Policy denials: 0.
