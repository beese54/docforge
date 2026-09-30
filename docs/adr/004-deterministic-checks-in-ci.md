# ADR-004: CI runs only deterministic checks; the model is never called in CI

## Status

Accepted

## Context

Documentation quality must be enforced on every change, but model calls are costly, non-deterministic and need credentials.

## Options Considered

- Run the agent in CI.
- Run only deterministic checks in CI; run the agent on demand (chosen).

## Decision

`docforge check` never calls the network or model. CI runs `docforge check --strict`. The agent runs on demand inside a sandbox.

## Rationale

Workflow header: "The model is never called in CI (the agent runs on demand in a sandbox)"; `checks.py` docstring: "Never calls the network or the model."

## Consequences

- CI is free and reproducible; `--strict` makes soft rules and adr_worthy drift fail the build.
- Semantic accuracy of docs is not verified by CI; only structure, links, ADR format, markers and drift.

## Related Components

`src/docforge/checks.py`, `.github/workflows/docforge.yml`, [TESTING.md](../TESTING.md)
