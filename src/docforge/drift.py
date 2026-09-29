"""Drift: code in an impact category changed but none of that category's docs did.

A commit can opt out with a trailer, e.g. `Docs-Impact: none — renamed a private helper`. The reason is
mandatory; an empty one is reported and ignored, so the escape hatch always leaves a written justification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from docforge import git, globs
from docforge.checks import Check, Context
from docforge.findings import Finding, Severity

OVERRIDE = re.compile(r"^none\s*[-–—:]\s*\S", re.IGNORECASE)


@dataclass(frozen=True)
class ChangeSet:
    all_files: frozenset[str]  # everything that changed, including overridden commits (doc edits still count)
    triggering: frozenset[str]  # files whose changes are NOT covered by a Docs-Impact override
    bad_trailers: tuple[str, ...]  # short SHAs of commits with a Docs-Impact trailer lacking a reason


def collect(ctx: Context, base: str) -> ChangeSet:
    all_files: set[str] = set()
    triggering: set[str] = set()
    bad: list[str] = []
    for commit in git.commits(ctx.root, base):
        all_files.update(commit.files)
        if any(OVERRIDE.match(v) for v in commit.docs_impact):
            continue
        if commit.docs_impact:
            bad.append(commit.sha[:8])
        triggering.update(commit.files)
    local = git.uncommitted(ctx.root)
    all_files.update(local)
    triggering.update(local)
    return ChangeSet(frozenset(all_files), frozenset(triggering), tuple(bad))


def evaluate(ctx: Context, changes: ChangeSet) -> list[Finding]:
    findings = [
        Finding("drift", Severity.WARN, sha, "Docs-Impact trailer has no reason; use 'Docs-Impact: none — <why>'")
        for sha in changes.bad_trailers
    ]
    for rule in ctx.cfg.impact:
        hits = sorted(f for f in changes.triggering if globs.match_any(f, rule.globs))
        if not hits or any(doc in changes.all_files for doc in rule.docs):
            continue
        severity = Severity.ERROR if (ctx.strict and rule.adr_worthy) else Severity.WARN
        shown = ", ".join(hits[:3]) + (f" (+{len(hits) - 3} more)" if len(hits) > 3 else "")
        findings.append(
            Finding(
                "drift", severity, hits[0],
                f"{rule.category} changed ({shown}) but none of {', '.join(rule.docs)} was updated. Update the docs, "
                "run `docforge agent impact`, or add a 'Docs-Impact: none — <reason>' trailer",
                category=rule.category,
            )
        )
    return findings


def make_check(base: str | None) -> Check:
    """A check bound to a base ref. `None` means: merge-base with main, if there is one."""

    def check_drift(ctx: Context) -> list[Finding]:
        if not ctx.cfg.impact:
            return []
        if not git.is_repo(ctx.root):
            return [Finding("drift", Severity.INFO, ".", "not a git repository; drift not checked")]
        ref = base or git.default_base(ctx.root)
        if ref is None:
            return [Finding("drift", Severity.INFO, ".", "no base to compare with; drift not checked")]
        try:
            resolved = git.resolve(ctx.root, ref)
        except git.GitError:
            return [Finding("drift", Severity.ERROR, ".", f"base ref '{ref}' not found (fetch with full history?)")]
        return evaluate(ctx, collect(ctx, resolved))

    return check_drift
