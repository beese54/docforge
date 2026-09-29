# Docs-as-Code Tool (working name: `docforge`) — Requirements Interrogation

Status: ANSWERED on 2026-09-29. All defaults accepted. #6 = beese54/markdown-visualiser. #16 = Sonnet tier, $39.90 of credit. The spec is drafted in `../specification.json`, `../definition_of_done.md` and `../progress_tracking.json`, and is waiting for approval.
Protocol: sonnet5-protocols Pattern M. After the spec is approved, the build goes through Pattern C, and the OpenShell hosting goes through Pattern AX (see `todo.md`).

## Phase 0 — Restating the ask
This is a tool for a solo developer who builds apps with AI ("vibe coding"). It does three jobs.
1. **Scaffold and enforce** a docs-as-code structure in any repo. That means README, CHANGELOG, `docs/*.md` and `docs/adr/`, with Markdown as the single source of truth.
2. **Keep the docs honest.** On each change, an AI agent runs a *documentation impact check* against the diff. It updates only the docs that are materially affected, drafts ADRs for decisions, checks the docs against the code, and marks anything unknown as `uncertain — verify with developer`.
3. **Publish.** It turns the Markdown into a formal, versioned technical manual PDF: Markdown → Pandoc → LaTeX template → PDF, with a table of contents, numbered figures and tables, and a version pulled from git.

A "hybrid reader" lets the developer view the living Markdown (with Mermaid diagrams) and the generated PDF side by side.

**Success looks like this:** a competent engineer clones a pilot repo and can answer the 13 "Final Objective" questions from the docs and PDF alone. CI goes red when the docs drift from the code.

## Feasibility verdict
- **Building it:** yes. Most of the parts already exist and should be reused, not rewritten:
  - Pandoc
  - an Eisvogel-style LaTeX template
  - mermaid-cli for diagrams
  - TeX Live or Tectonic
  - markdownlint and lychee for linting and link checks
  - the MADR ADR format

  **Honest overlap:** Quarto already covers most of the "MD → LaTeX → PDF + preview" part. What is actually new here is the *agent layer*: impact checks, drift detection, ADR capture, and the rule to "mark it uncertain instead of guessing". The conventions and templates around it are new too.
- **Hosting in OpenShell: partly.** OpenShell is a *sandbox runtime for agents*, not a web or app host.
  - ✅ **Good fit:** the documentation agent. It gets a read-only copy of the repo, writes only to a docs branch, and can only reach the model API and the git remote. The PDF build also fits: a sandbox with no network and a pandoc + TeX image.
  - ❌ **Poor fit:** serving the reader UI to users. Run it locally, or publish a static site (GitHub Pages).
  - ⚠️ On Windows it only runs through WSL2, which is experimental. TeX Live is several GB, so it needs a custom sandbox image (Tectonic keeps that small).

## Proposed architecture (default, before your answers)
```
docforge CLI (Python)
 ├─ init    → scaffold docs/, adr/, templates, CI workflow, CLAUDE.md doc rules
 ├─ check   → lint, links, required sections, "uncertain" count, drift (code changed ⇒ mapped doc not touched)
 ├─ build   → pandoc + LaTeX template → versioned PDF (git tag + short SHA)
 ├─ serve   → local reader: rendered MD + Mermaid | PDF preview, auto-reload
 └─ agent   → impact check / ADR draft / verify-against-code → opens a PR (never pushes to main)
Runtime:  CI (GitHub Actions) runs check + build;  OpenShell sandbox runs `agent` (+ optional build)
```

## Phase 1 — Question matrix
Reply like this: "defaults fine except #N …"

| # | Category | Question | Proposed default | Why it matters |
|---|---|---|---|---|
| 1 | SCOPE | What form should the "hybrid reader" take? | CLI + local web preview (MD/Mermaid next to PDF). Not a desktop app | Changes the stack and effort by roughly 5× |
| 2 | SCOPE | Which way does LaTeX conversion go? | One-way, MD → LaTeX → PDF, as your spec says. Importing existing `.tex` is out of MVP | Two-way conversion is a hard, lossy problem |
| 3 | SCOPE | Build on Pandoc, or on Quarto? | Pandoc + our own LaTeX template, as in your spec | Quarto is faster to ship; Pandoc gives more control |
| 4 | SCOPE | What is the MVP? | `init` + `check` + `build` + agent impact-check. The reader (`serve`) comes in v2 | Keeps phase 1 to about 1–2 weeks |
| 5 | USERS | Is this just for you, or for others (open source / product)? | You first, but structured so it can be open-sourced | Affects packaging, config and polish |
| 6 | USERS | Which real repo will be the pilot? | One of your existing vibe-coded projects (please name it) | Tests are only meaningful against real code |
| 7 | DATA | Are the repos private, and is it OK to send code to the model API? | Private; code goes only to the Claude API, nowhere else | Decides the egress policy and provider |
| 8 | BEHAVIOR | When should the agent run? | On demand plus on every PR/push (CI). No 24/7 poller | "Continuous" in OpenShell is optional, not required |
| 9 | BEHAVIOR | What can the agent write? | It only proposes, via a branch/PR you review. It never commits to main | The human gate: docs are the source of truth |
| 10 | BEHAVIOR | Should drift warn or block? | Warn locally. CI fails only when ADR-worthy files change (deps, schema, auth, infra) without a doc change | Too strict becomes noise, too lax is pointless |
| 11 | FAILURE | What happens if the model API is down or over budget? | Non-AI checks and the build still run. The agent step is skipped with a warning and never blocks | Keeps the tool usable offline and at no cost |
| 12 | NON-FUNC | What should the PDF look like? | Clean, neutral A4 template with a version, date and SHA in the footer. Unless you have a logo, colours or fonts | "Corporate styling" needs actual brand inputs |
| 13 | NON-FUNC | Can Mermaid diagrams be rendered for the PDF with headless Chromium (mermaid-cli)? | Yes, as SVG → PDF | Adds about 300 MB to the build image |
| 14 | CONSTRAINT | What is OpenShell for here? | Sandboxing the agent + build only. The reader runs locally or on GitHub Pages | OpenShell is not a web host |
| 15 | CONSTRAINT | Which git host and CI? | GitHub + GitHub Actions | Drives the PR and CI integration |
| 16 | CONSTRAINT | Which model and budget? | Claude Sonnet tier via API, with a hard monthly spend cap (you set the amount) | Cost of running on every PR |
| 17 | CONSTRAINT | What language should the tool be written in? | Python (packaged with uv) | Pandoc and the OpenShell SDK both work well from Python |
| 18 | CONSTRAINT | Is developing inside WSL2 on this Windows machine OK? | Yes (Ubuntu-24.04 is already installed) | OpenShell requires it on Windows |
| 19 | DATA | Does docforge document itself with its own system? | Yes. Its own ADRs are the first ones (e.g. ADR-001 Pandoc vs Quarto) | This is the dogfood test |

## Next (after answers)
Phase 2: `specification.json` + `definition_of_done.md`. Phase 3: adversarial self-check. Phase 4: approval gate, then the Pattern C build.
