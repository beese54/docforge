# DoD 6.4: claims audit, T11 bootstrap of markdown-visualiser

Method: 20 concrete, checkable claims were taken from the generated docs, weighted towards SECURITY and DEPLOYMENT, where an error costs most. Each was checked against the pilot source at `cc34345` by reading the cited file. This is in addition to the automated check: 298 `<!-- sources -->` citations, and every cited path exists.

| # | Doc | Claim | Evidence | Verdict |
|---|---|---|---|---|
| 1 | SECURITY | PDF body limit is 20 MB | `server/index.ts:20` `PDF_BODY_LIMIT = 20 * 1024 * 1024` | True |
| 2 | SECURITY | Concurrency is limited to 1–4 by p-limit | `server/pdf.ts:88` `pLimit(Math.max(1, Math.min(4, cpus().length)))` | True |
| 3 | SECURITY/RATE | Queue cap is 4 × concurrency, then 429 | `server/pdf.ts:136`; `server/index.ts:93` sends 429 + retry-after | True |
| 4 | SECURITY | 20 s setContent, 20 s page default, 30 s overall deadline | `server/pdf.ts:30-33` | True |
| 5 | SECURITY | Header title is HTML-escaped and cut to 120 characters | `server/pdf.ts:217,225` | True |
| 6 | SECURITY | `javaScriptEnabled: false` | `server/pdf.ts:145` | True |
| 7 | SECURITY | Routing allows only `data:`, `blob:`, `about:` | `server/pdf.ts:118` | True |
| 8 | SECURITY | Service workers are blocked | `server/pdf.ts:155` | True |
| 9 | SECURITY | nosniff, referrer and COOP headers are set; no CSP | `server/index.ts:47-49`; no CSP header anywhere | True |
| 10 | SECURITY | `trustProxy: false` | `server/index.ts:31` | True |
| 11 | SECURITY | Env vars read: PORT, HOST, STATIC_ROOT, LOG_LEVEL, NODE_ENV | The code reads the first four. `NODE_ENV` is only *set* (Dockerfile:24, compose:20) and never read by app code | **Imprecise** (harmless) |
| 12 | SECURITY | `format` is Letter or else A4; `landscape` only when exactly `true` | `server/index.ts:74,81` | True |
| 13 | SECURITY | The sanitiser strips script/style/iframe/object/embed/link/meta/base/form | `src/pipeline/sanitize.ts:156` | True |
| 14 | SECURITY | href protocols are http/https/mailto/tel/irc/ircs/xmpp | `src/pipeline/sanitize.ts:147` | True |
| 15 | SECURITY | Raster `data:image/*` only; SVG excluded | `src/pipeline/sanitize.ts:118` | True |
| 16 | SECURITY/DATA | Ingest limits: 2000 files, 200 MB, 10 MB per file | `src/types/domain.ts:108-110` | True |
| 17 | SECURITY | Generic 503 body; details only in logs | `server/index.ts:105` | True |
| 18 | SECURITY/DEPLOY | Loopback-only publish, read_only, cap_drop, no-new-privileges, ipc host | `docker-compose.yml:12,16,23,26,29` | True |
| 19 | DEPENDENCIES | `playwright-core` pinned to the base image version | `package.json:27` 1.62.1 = `Dockerfile:22` v1.62.1 | True |
| 20 | ADR-004 | Reading order is a composite string key: dir.explicit.index.numeric.natural | `src/ingest/ordering.ts:80-92` | True |

Also verified: the three discrepancies the agent raised. `printSchema` is unused. `mixed-markers` only normalises spacing. `tests/adversarial/pdf-endpoint.sh` is missing.

**Result: 19/20 true, 1/20 imprecise, 0/20 false.** No invented behaviour was found. Where the agent could not verify something, it wrote "uncertain — verify with developer" (22 markers).
