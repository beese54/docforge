# ADR-006: Build the manual with pandoc, a Lua filter, tectonic and mermaid-cli

## Status

Accepted

## Context

Repository Markdown must become a versioned PDF manual, including Mermaid diagrams and cross-file links that make sense on paper.

## Options Considered

Recorded in `tasks/docs-as-code-requirements.md` (question #3) and the T2/T6 commits:

- **Quarto.** Markdown → LaTeX → PDF with Mermaid, cross-references and a preview built in. Fastest to ship, but it brings its own project format and a large toolchain, and gives less control over how multi-file links are resolved.
- **Pandoc with a fully custom LaTeX template (Eisvogel-style).** Maximum control of the look, but a large template to maintain.
- **Pandoc with its default LaTeX template, plus a small include-in-header file and a Lua filter** (chosen).
- **TeX engines:** a full TeX Live install (several GB, needs downloads at build time) or **tectonic** (single binary, fetches only the packages a document uses, and its cache can be pre-warmed for offline builds).

<!-- sources: tasks/docs-as-code-requirements.md, specification.json, src/docforge/templates/manual.yaml, sandbox/build.Dockerfile -->


## Decision

`docforge build` runs pandoc over the configured chapters with `--defaults`, a generated header and `docforge.lua`, producing LaTeX and a PDF via tectonic. The filter renders Mermaid blocks with `mmdc` into numbered figures, and rewrites links: to files in the manual become internal links, other repo paths become plain text. The title carries `git describe` version, date and SHA. Defaults can be overridden by files in `documentation/`.

## Rationale

- The source brief asked for Pandoc and for Markdown to remain the single source of truth. Pandoc reads the same GitHub-flavoured Markdown the repository renders, so no second format is introduced.
- The default template plus a ~20-line header (`manual-header.tex`) already gives TOC, numbered sections, figures, headers and footers. A custom template would add maintenance without changing the result (deviation from the original spec, recorded in commit `cfd3dca`).
- A Lua filter is needed anyway: pandoc does not rewrite links whose path does not literally match an input, and relative repo paths mean nothing on paper (`build.py`, `docforge.lua`).
- tectonic keeps the build image small and, with its cache warmed at image build time, lets the manual build with **no network**, which is what the build sandbox policy requires (`sandbox/build-policy.yaml`, red-team 5.4b).

<!-- sources: src/docforge/build.py, src/docforge/templates/docforge.lua, src/docforge/templates/manual-header.tex, sandbox/build-policy.yaml, evidence/pilot-runs.md -->


## Consequences

- Requires pandoc, tectonic, mermaid-cli, Chromium; build image bakes them in for offline use ([ADR-003](003-openshell-sandboxes.md)).
- Diagram failures are warnings unless `--strict`.

## Related Components

`src/docforge/build.py`, `src/docforge/templates/docforge.lua`, `sandbox/build.Dockerfile`
