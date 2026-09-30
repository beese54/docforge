# DoD 6.6: can a new engineer answer the 13 questions from the docs alone?

Pilot: markdown-visualiser, branch `docforge/bootstrap-24c6b4f` (1,082 lines of docs plus 8 ADRs).

| # | Question | Answered in | Verdict |
|---|---|---|---|
| 1 | What does this system do? | README "Purpose"; ARCHITECTURE "Overview" | Yes |
| 2 | How does it work? | HOW_IT_WORKS: 5 workflows (drop and build, render and read, HTML export, PDF export, health/shutdown); ARCHITECTURE "Information Flow" | Yes |
| 3 | Why was it designed this way? | 8 ADRs (001–008); DESIGN "Design Principles" | Yes |
| 4 | How do I run it? | README "Local Development"; MAINTENANCE "Starting and Stopping" | Yes |
| 5 | How do I deploy it? | DEPLOYMENT "Build / Deploy / Configuration / Rollback"; README "Deployment" | **Partly.** Only the local `docker compose` path exists. Production host, release and rollback are marked uncertain, because the repo defines none. |
| 6 | How do I test it? | TESTING (9 sections, incl. "Running Tests", "Required Before Changes"); README "Running Tests" | Yes |
| 7 | Where is the data stored? | DATA_MODEL: in memory only, no database; SECURITY "Sensitive Data" | Yes |
| 8 | What external systems does it depend on? | ARCHITECTURE "External Systems"; DEPENDENCIES "Critical Dependencies" | Yes |
| 9 | What could break? | MAINTENANCE: 4 fragile areas + "Known Technical Debt" (incl. unused `printSchema`) | Yes |
| 10 | How do I troubleshoot it? | TROUBLESHOOTING: 11 problems, 5 kept as historical lessons | Yes |
| 11 | Which components are fragile? | MAINTENANCE "Fragile Areas": sanitiser order, print service, folder walk/ordering, export serialisation | Yes |
| 12 | How do I safely modify it? | TESTING "Required Before Changes"; MAINTENANCE "Making Production Changes"; each fragile area lists what must be tested | Yes |
| 13 | Why were important technical decisions made? | ADR-001…008, each with Context / Options / Rationale / Consequences and cited code | Yes |

**Result: 12/13 fully answered, 1/13 partly.** Deployment beyond local Compose is marked uncertain. That is the honest outcome: the repository contains no production deployment to document, so only the owner can fill it in.
