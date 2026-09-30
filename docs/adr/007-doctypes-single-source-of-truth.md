# ADR-007: One table defines the documentation set for scaffolding, checking and the agent prompt

## Status

Accepted

## Context

The scaffold, the checker and the agent's instructions must agree on which documents and sections exist.

## Options Considered

- Separate lists per feature.
- A single table in `doctypes.py` (chosen).

## Decision

`doctypes.DOC_TYPES` lists each document, purpose and required H2 sections. `init` renders skeletons from it, `check_sections` verifies against it, and `agent/prompts.py` builds the system prompt from it. The "uncertain" marker text is defined there too.

## Rationale

Module docstring: "so the two can never drift apart".

## Consequences

- Changing a section name updates all three consumers, but existing docs must be updated too or `check` fails.
- Custom documents beyond the set are only checked by link/uncertain rules (via `docs/**`).

## Related Components

`src/docforge/doctypes.py`, `src/docforge/init.py`, `src/docforge/checks.py`, `src/docforge/agent/prompts.py`
