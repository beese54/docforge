# ADR-002: Hand-written agent loop with a hard budget guard

## Status

Accepted

## Context

Model calls cost money. Spend must be capped per run and per month without relying on the model's cooperation.

## Options Considered

- The SDK's tool runner.
- A manual loop with a pre-call guard (chosen).

## Decision

`agent/runner.py` runs the loop manually so that every call passes through `BudgetGuard`. Before each call the guard counts input tokens and sets `max_tokens` so the worst case (all input at cache-write rate, all output used) fits the remaining allowance; if under 2,048 tokens fit, the call is refused. Interrupted streams are charged worst-case. Per-command turn limits (impact 40, adr 20, bootstrap 120). Spend goes to `~/.docforge/usage.jsonl`.

## Rationale

Stated in the module docstrings: "Manual (not the SDK tool runner) so every call passes through the budget guard first" and "Hard spend caps, enforced by construction".

## Consequences

- The cap cannot be exceeded by a single call.
- Prices and model id are hard-coded; a stale price table weakens the guarantee.
- The ledger over-states rather than under-states interrupted calls.

## Related Components

`src/docforge/agent/runner.py`, `src/docforge/agent/budget.py`, `docforge.toml` `[budget]`
