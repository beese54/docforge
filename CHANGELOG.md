# Changelog

All meaningful changes to this project are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Git history is not a substitute.

## [Unreleased]

### Added

- Bootstrapped the documentation set: README, the 12 `docs/*.md` files and ADRs 001–007. <!-- sources: docs/adr/, docforge.toml -->
- **docforge Console** (`docforge serve`, optional `[console]` extra): a local-only web UI with Repos health, repo detail, agent runs (replays of recorded runs, or live runs in OpenShell with streamed progress), Review, Apply / Push / Open PR, the PDF manual, the security scorecard and usage. See ADR-008 and `docs/DEMO.md`. <!-- sources: src/docforge/console/, docs/adr/008-local-console-over-cli.md -->
- The agent prints each trace line as it happens when `DOCFORGE_PROGRESS` is set; `run-agent.sh` sets it inside the sandbox. <!-- sources: src/docforge/agent/runner.py, sandbox/run-agent.sh -->

### Changed

- README rewritten from a two-line stub into the eight required sections; no deep material existed to move. <!-- sources: README.md -->

### Security

- The console binds 127.0.0.1 only, checks the Host header, needs a per-launch token (cookie for pages, header for actions), and pushes only `docforge/*` branches it created, never with force. <!-- sources: src/docforge/console/app.py, src/docforge/console/publish.py -->

### Removed
