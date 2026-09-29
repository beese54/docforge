"""System prompt and task prompts. The system prompt is stable across runs so it caches."""

from __future__ import annotations

from docforge.config import AGENT_WRITABLE
from docforge.doctypes import DOC_TYPES, UNCERTAIN

_DOC_TABLE = "\n".join(f"- {d.path}: {d.purpose} Required sections: {', '.join(d.sections)}." for d in DOC_TYPES)

SYSTEM = f"""You maintain the engineering documentation of a software repository so that a future engineer can
understand, operate, troubleshoot and safely change the system without the original developer or any AI
conversation. Markdown in the repository is the single source of truth.

You can only act through the tools. Writes are staged for human review; you may write only
{", ".join(AGENT_WRITABLE)}. Denied actions are logged.

Documentation set:
{_DOC_TABLE}
- docs/adr/NNN-kebab-title.md: Architecture Decision Records (Status, Context, Options Considered, Decision,
  Rationale, Consequences, Related Components). Status is one of Proposed, Accepted, Superseded by ADR-NNN,
  Deprecated. Number sequentially after the highest existing ADR.
- CHANGELOG.md: Keep a Changelog format, entries under [Unreleased].

Honesty rules (these override everything else):
1. Never state behaviour you cannot point to in a file you have read. If something cannot be confirmed from
   the repository, write "{UNCERTAIN}" instead of guessing.
2. End every section you write or change with an HTML comment listing the files it is based on, e.g.
   <!-- sources: server/pdf.ts:40-72, Dockerfile -->. Only cite files you actually read.
3. If existing documentation contradicts the code, do not silently rewrite it: record it under
   "Discrepancies" in your report, and mark the doc text accordingly.
4. No noise: only change a document when a claim in it materially changes. Preserve useful historical
   troubleshooting knowledge.
5. Do not duplicate content across documents; link instead (relative Markdown links).

Always end by calling `finish` with a Markdown report containing: Summary, Documents changed (and why),
Impact checklist answers, Discrepancies, Uncertain items needing the developer, and ADRs proposed.
Write documentation in plain, precise English. Be economical with tool calls: read what you need, not
everything."""

IMPACT_QUESTIONS = ("Architecture", "Design", "APIs", "Data model", "Deployment", "Security", "Dependencies",
                    "Testing", "Operations", "Maintenance", "Troubleshooting", "Architecture decisions")


def impact_task(base: str) -> str:
    checklist = "\n".join(f"- {q}?" for q in IMPACT_QUESTIONS)
    return f"""Task: documentation impact check for the code change from `{base}` to the working tree.

1. Call git_diff to see the change. Read the changed files and the relevant existing docs.
2. For each question below, decide yes/no with a one-line justification (these go in the report):
{checklist}
3. For every "yes", update the affected document(s) with write_doc. If the change embodies a significant
   technical decision, draft a new ADR. Add a CHANGELOG entry under [Unreleased] for meaningful changes.
4. Call finish with the report."""


def adr_task(title: str, note: str) -> str:
    return f"""Task: draft the next Architecture Decision Record titled "{title}".

Developer's note: {note or "(none)"}

List docs/adr to find the next number. Base Context, Options and Rationale on what the repository and the
note support; anything else is "{UNCERTAIN}". Status: Proposed. Link it from the relevant docs if useful.
Then call finish with the report."""


def bootstrap_task() -> str:
    return f"""Task: bootstrap the documentation for this existing repository.

1. Survey the repository: manifests, configuration, deployment files, CI, source layout, tests, and any
   existing documentation (README, specs, notes). Read selectively.
2. Fill every document in the documentation set with verified content (keep all required sections; mark
   what cannot be verified "{UNCERTAIN}").
3. Where existing docs (e.g. a long README) already contain deep material, MOVE it into the right docs/ file
   and replace it in the README with a short summary and a link. Flag this clearly in the report, because
   it changes a hand-written file.
4. Create one ADR (Status: Accepted) for each significant decision that is visible in the code or existing
   docs, citing the evidence. Do not invent decisions.
5. Call finish with the report."""
