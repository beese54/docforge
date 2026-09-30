## Summary
All 12 `docs/*.md` files were empty templates. I filled each with content checked against the code, and staged them for review. I also staged a restructured README, 8 ADRs and a CHANGELOG entry. Anything I could not confirm is marked "uncertain — verify with developer".

I did not run any tests, builds or containers. Test counts (121 unit tests, 11 security checks) and the "verified by probe" claims come from `README.md` and `tasks/todo.md`, and the docs say so.

## Documents changed (and why)
- **README.md — hand-written file changed.** The old README held deep material, which I moved into `docs/`. The remaining README has the required sections plus the Meng To credit, screenshots and licence, which I kept as written.
  - Architecture diagram and trust-boundary text → `docs/ARCHITECTURE.md`, `docs/DESIGN.md` and ADR-002.
  - Security controls table → `docs/SECURITY.md`.
  - Verification tables → `docs/TESTING.md`.
  - Project layout → `docs/ARCHITECTURE.md`.
  - Limits → `docs/DATA_MODEL.md`.
  - Image-size follow-up → `docs/MAINTENANCE.md`.
  - Please review the README diff.
- **docs/ARCHITECTURE.md, DESIGN.md, HOW_IT_WORKS.md, DATA_MODEL.md, API.md, SECURITY.md, DEPLOYMENT.md, TESTING.md, OPERATIONS.md, MAINTENANCE.md, TROUBLESHOOTING.md, DEPENDENCIES.md:** filled from empty templates.
- **docs/adr/001–008:**
  - 001 single client-side pipeline
  - 002 sanitiser placed right after `rehype-raw`
  - 003 contained, unauthenticated print service
  - 004 composite string sort key
  - 005 report every markdown repair
  - 006 `webkitGetAsEntry` for folder drops
  - 007 official Playwright image, non-root
  - 008 self-hosted fonts, no third-party requests
- **CHANGELOG.md:** entries added under `[Unreleased]`.

## Impact checklist answers
- **Dependencies:** documented in `DEPENDENCIES.md`. No dependency files were changed.
- **Deployment:** documented in `DEPLOYMENT.md` and `OPERATIONS.md`. No deployment files were changed.
- **Data model:** documented in `DATA_MODEL.md`. It is in-memory only, with no database and no migrations.
- **Security:** documented in `SECURITY.md`, with the `printSchema` finding below.
- **API:** documented in `API.md`.
- **Testing:** documented in `TESTING.md`.
- **ADR-worthy decisions:** eight ADRs proposed.

## Discrepancies
1. **`printSchema` is not used.** `src/pipeline/sanitize.ts` describes it as a stricter schema "applied server-side before the print service hands HTML to Chromium". A grep of `server/`, `src/` and `tests/` finds no use of it. The server has no sanitiser, and the README says the server has no markdown dependencies. I recorded this in SECURITY, MAINTENANCE and ADR-003, and I did not touch the code.
2. **`mixed-markers` repair rule.** The README says it normalises mixed bullet markers. The code only normalises list tight/loose spacing, because mdast does not keep marker characters. I documented the code's behaviour.
3. **Missing script.** `definition_of_done.md` cites `tests/adversarial/pdf-endpoint.sh`. It does not exist. The probe is `tests/e2e/adversarial.mjs`, run through `tests/e2e/run.sh`.
4. **Test filters.** `definition_of_done.md` uses filters such as `npm test -- links` and `-- sanitize`. There are no matching test files in the file list. The filters may match `pipeline.test.ts` or another file, but I did not read those.
5. **Project name.** `docforge.toml` names the project `pilot-live`. The package is `markdown-visualiser`.
6. **Loopback binding.** The README says the app has "no authentication because it has nothing to authenticate". The service is still a headless browser that renders posted HTML. I kept both statements and stressed the loopback binding.

## Uncertain items needing the developer
- Where production runs, and the release, tagging and rollback process. Nothing beyond `docker compose` is defined.
- Whether any CI runs the application tests. Only the `docforge` workflow exists.
- Whether PDF export works from `npm run dev`. I did not read `vite.config.ts`.
- Whether a Content-Security-Policy is intended.
- Whether Chromium writes document content to `/tmp`.
- Whether Fastify's default request logging is left on.
- The `specification.json` schemas and the `docforge` install source. The workflow marks the latter uncertain.
- I did not read these files, so the docs cite them only through other sources: the Shiki, Mermaid and assets plugins, the reader components and the unit test files. Claims about Mermaid `securityLevel: 'strict'`, the Shiki JS regex engine, the image placeholder and the 13 hostile-payload tests come from `tasks/todo.md` and `definition_of_done.md`.
- Escalation contacts and alerting.

## ADRs proposed
ADR-001 to ADR-008, all Status: Accepted, each citing evidence from the code or existing docs. I did not create an ADR for the Shiki JS regex engine, because I did not read the plugin.


---
Run `dcd26d9a9181` (bootstrap): 28 model turn(s), cost $1.4001. Files in patch: CHANGELOG.md, README.md, docs/API.md, docs/ARCHITECTURE.md, docs/DATA_MODEL.md, docs/DEPENDENCIES.md, docs/DEPLOYMENT.md, docs/DESIGN.md, docs/HOW_IT_WORKS.md, docs/MAINTENANCE.md, docs/OPERATIONS.md, docs/SECURITY.md, docs/TESTING.md, docs/TROUBLESHOOTING.md, docs/adr/001-single-client-side-markdown-pipeline.md, docs/adr/002-sanitiser-immediately-after-rehype-raw.md, docs/adr/003-contained-print-service.md, docs/adr/004-composite-string-sort-key-for-reading-order.md, docs/adr/005-report-every-markdown-repair.md, docs/adr/006-webkitgetasentry-for-folder-drop.md, docs/adr/007-playwright-official-image-non-root.md, docs/adr/008-self-hosted-fonts-no-third-party-requests.md. Policy denials: 0.
