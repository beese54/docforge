# ADR-001: The agent proposes patches; a human applies them, on a doc-path allowlist

## Status

Accepted

## Context

An LLM agent that edits a repository directly could change code or leak content through file writes. The tool is meant to maintain documentation only.

## Options Considered

- Let the agent write files directly.
- Let the agent write only docs, directly.
- Stage writes in memory, output a patch, require a human to apply it (chosen).

## Decision

`ToolLayer.write_doc` only stages content in memory and only for `README.md`, `CHANGELOG.md`, `docs/**` Markdown files. The runner turns staged content into `docforge.patch`. `docforge apply` re-checks every path in the patch, commits on a new branch and never pushes. The allowlist `AGENT_WRITABLE` is deliberately not configurable.

## Rationale

Evidence: comments in `agent/policy.py` ("Nothing here writes to disk"), `apply.py` ("a patch that was edited, or produced by something other than the sandboxed agent, still cannot touch code") and `config.py` ("Deliberately not configurable"). Broader rationale beyond these comments: uncertain — verify with developer.

## Consequences

- Safe by default; every change gets human review.
- Extra step for the user; patches can fail to apply if docs change after the run.
- Code files can never be updated by the agent.

## Related Components

`src/docforge/agent/policy.py`, `src/docforge/apply.py`, `src/docforge/config.py`, [SECURITY.md](../SECURITY.md)
