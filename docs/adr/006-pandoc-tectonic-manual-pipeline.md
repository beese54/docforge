# ADR-006: Build the manual with pandoc, a Lua filter, tectonic and mermaid-cli

## Status

Accepted

## Context

Repository Markdown must become a versioned PDF manual, including Mermaid diagrams and cross-file links that make sense on paper.

## Options Considered

Alternatives are not recorded in the repository (uncertain — verify with developer).

## Decision

`docforge build` runs pandoc over the configured chapters with `--defaults`, a generated header and `docforge.lua`, producing LaTeX and a PDF via tectonic. The filter renders Mermaid blocks with `mmdc` into numbered figures, and rewrites links: to files in the manual become internal links, other repo paths become plain text. The title carries `git describe` version, date and SHA. Defaults can be overridden by files in `documentation/`.

## Rationale

Visible in `build.py` and `docforge.lua` comments (pandoc does not rewrite links whose path does not match an input literally; relative repo paths mean nothing on paper). Choice of tectonic over other TeX engines: uncertain — verify with developer.

## Consequences

- Requires pandoc, tectonic, mermaid-cli, Chromium; build image bakes them in for offline use ([ADR-003](003-openshell-sandboxes.md)).
- Diagram failures are warnings unless `--strict`.

## Related Components

`src/docforge/build.py`, `src/docforge/templates/docforge.lua`, `sandbox/build.Dockerfile`
