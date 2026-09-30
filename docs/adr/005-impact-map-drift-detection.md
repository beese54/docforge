# ADR-005: Detect documentation drift with a configurable impact map and a commit-trailer escape hatch

## Status

Accepted

## Context

Docs go stale when code changes without them. A tool needs a cheap, deterministic signal.

## Options Considered

- Rely on reviewers.
- Map code globs to docs and flag changes with no matching doc change (chosen).

## Decision

`docforge.toml` holds `[[impact]]` rules (category, globs, docs, `adr_worthy`). `docforge check` inspects commits in `base..HEAD` plus uncommitted files; if a rule's globs match and none of its docs changed, it warns, or errors under `--strict` when `adr_worthy`. A commit can opt out with `Docs-Impact: none — <reason>`; a missing reason is reported and ignored. `docforge init` guesses the initial map from files present.

## Rationale

Module docstring of `drift.py`; the comment in `docforge.toml`. Choice of globs over other techniques: uncertain — verify with developer.

## Consequences

- The map must be maintained; the current one was guessed and needs review.
- Drift shows only that a doc file changed, not that it is correct.
- Needs full git history in CI (`fetch-depth: 0`).

## Related Components

`src/docforge/drift.py`, `src/docforge/init.py`, `docforge.toml`
