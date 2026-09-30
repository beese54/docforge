# Data Model

> Entities, relationships, constraints, ownership and business rules.

## Overview

docforge has no database. Its persistent data is a JSON-lines usage ledger and the files it reads or produces in the target repository.

<!-- sources: src/docforge/agent/budget.py -->

## Entities

- **UsageRecord** (one JSON object per line in `usage.jsonl`): `ts`, `run_id`, `command`, `model`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`, `note`.
- **Config** (`docforge.toml`): project name/title, required docs, impact rules (`category`, `globs`, `docs`, `adr_worthy`), manual chapters, budget, uncertain limit.
- **Finding**: rule, severity, file, message, optional line (in-memory).
- **Run outputs**: `docforge.patch`, `docforge.partial.patch`, `report.md`, `policy.log`, `trace.log`, `run.json` (`run_id`, `command`, `status`, `cost_usd`, `turns`, `files`).
- **ADR files**: `docs/adr/NNN-kebab-title.md`.

<!-- sources: src/docforge/agent/budget.py, src/docforge/config.py, src/docforge/agent/runner.py, src/docforge/checks.py -->

## Relationships

Records sharing a `run_id` belong to one agent run; `run.json` sits beside the patch and is read by `apply` to name the branch. Impact rules map file globs to doc paths.

<!-- sources: src/docforge/apply.py, src/docforge/drift.py -->

## Constraints and Indexes

Config: unknown keys rejected; category names unique; budgets positive numbers; `max_markers` non-negative integer. ADRs: 3-digit number, no duplicates, no gaps, valid status. No indexes.

<!-- sources: src/docforge/config.py, src/docforge/checks.py -->

## Ownership and Retention

The ledger is per-user, at `$DOCFORGE_HOME` or `~/.docforge`, append-only; no rotation or retention policy exists in code. Run outputs default to `documentation/build/agent` (git-ignored via `documentation/build/`).

<!-- sources: src/docforge/agent/budget.py, src/docforge/init.py, src/docforge/cli.py -->

## Migrations

None. The ledger format has no version field; a changed `UsageRecord` would break reading older lines (`UsageRecord(**json)`), so add fields with defaults.

<!-- sources: src/docforge/agent/budget.py -->

## Business Rules

- Monthly spend is the sum of ledger records whose timestamp starts with the current `YYYY-MM`.
- Allowance = min(per-run cap − run spent, monthly cap − month spent before run − run spent).
- Default caps: impact $0.50, adr $0.30, bootstrap $3.00 per run; $10.00 per month.
- Interrupted calls are recorded at worst-case cost.

<!-- sources: src/docforge/agent/budget.py, src/docforge/config.py -->
