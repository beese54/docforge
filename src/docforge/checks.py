"""`docforge check`: deterministic documentation checks. Never calls the network or the model."""

from __future__ import annotations

import os
import posixpath
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

from docforge import markdown
from docforge.config import Config
from docforge.doctypes import BY_PATH, UNCERTAIN_RE
from docforge.findings import Finding, Severity

ADR_DIR = "docs/adr"
ADR_NAME = re.compile(r"^(\d{3})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
ADR_STATUSES = ("Proposed", "Accepted", "Superseded", "Deprecated")
_EXTERNAL = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|//)")
_ADR_REF = re.compile(r"ADR-(\d{3})")


@dataclass
class Context:
    cfg: Config
    strict: bool = False
    _parsed: dict[str, markdown.Document | None] = field(default_factory=dict)

    @property
    def root(self) -> Path:
        return self.cfg.root

    def doc(self, rel: str) -> markdown.Document | None:
        """Parsed Markdown for a repo-relative path, or None if it does not exist."""
        if rel not in self._parsed:
            path = self.root / rel
            self._parsed[rel] = (
                markdown.parse(path.read_text(encoding="utf-8", errors="replace")) if path.is_file() else None
            )
        return self._parsed[rel]

    def doc_paths(self) -> list[str]:
        """Documents under check: the configured set plus everything in docs/."""
        paths = {p for p in self.cfg.required_docs if (self.root / p).is_file()}
        docs_dir = self.root / "docs"
        if docs_dir.is_dir():
            paths.update(p.relative_to(self.root).as_posix() for p in docs_dir.rglob("*.md"))
        return sorted(paths)

    def soft(self) -> Severity:
        """Severity for rules that warn locally and fail CI."""
        return Severity.ERROR if self.strict else Severity.WARN


def exists_exact(root: Path, rel: str) -> bool:
    """Path exists with this exact letter case (case-insensitive filesystems would otherwise hide CI failures)."""
    current = root
    for part in [p for p in rel.split("/") if p]:
        try:
            if part not in os.listdir(current):
                return False
        except (NotADirectoryError, FileNotFoundError):
            return False
        current = current / part
    return True


def check_structure(ctx: Context) -> list[Finding]:
    return [
        Finding("structure", Severity.ERROR, rel, "required document is missing (run `docforge init`)")
        for rel in ctx.cfg.required_docs
        if not (ctx.root / rel).is_file()
    ]


def check_sections(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    for rel, doctype in BY_PATH.items():
        doc = ctx.doc(rel)
        if doc is None:
            continue
        present = {h.text.lower() for h in doc.headings if h.level == 2}
        for section in doctype.sections:
            if section.lower() not in present:
                findings.append(Finding("sections", ctx.soft(), rel, f"missing required section '## {section}'"))
    return findings


def check_links(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    for rel in ctx.doc_paths():
        doc = ctx.doc(rel)
        assert doc is not None
        base_dir = posixpath.dirname(rel)
        for link in doc.links:
            if _EXTERNAL.match(link.target):
                continue
            path_part, _, anchor = link.target.partition("#")
            path_part = unquote(path_part.split("?", 1)[0])
            target_doc: markdown.Document | None
            if not path_part:
                target_rel, target_doc = rel, doc
            else:
                joined = path_part.lstrip("/") if path_part.startswith("/") else posixpath.join(base_dir, path_part)
                target_rel = posixpath.normpath(joined)
                if target_rel.startswith(".."):
                    findings.append(Finding("links", Severity.ERROR, rel, f"link leaves the repository: {link.target}",
                                            link.line))
                    continue
                if not exists_exact(ctx.root, target_rel):
                    findings.append(Finding("links", Severity.ERROR, rel, f"broken link: {link.target}", link.line))
                    continue
                target_doc = ctx.doc(target_rel) if target_rel.lower().endswith(".md") else None
            if anchor and target_doc is not None and unquote(anchor).lower() not in {
                a.lower() for a in target_doc.anchors
            }:
                findings.append(Finding("links", Severity.ERROR, rel, f"missing anchor: {link.target}", link.line))
    return findings


def _adr_status(doc: markdown.Document) -> str | None:
    for line in doc.section_lines("Status"):
        if line.strip():
            return line.strip()
    return None


def check_adr(ctx: Context) -> list[Finding]:
    adr_dir = ctx.root / ADR_DIR
    if not adr_dir.is_dir():
        return []
    findings: list[Finding] = []
    numbers: dict[int, str] = {}
    records: list[tuple[str, int, markdown.Document]] = []
    for path in sorted(adr_dir.glob("*.md")):
        rel = path.relative_to(ctx.root).as_posix()
        if path.name.startswith("000"):
            continue  # the template
        m = ADR_NAME.match(path.name)
        if not m:
            findings.append(Finding("adr", Severity.ERROR, rel, "ADR file name must be NNN-kebab-title.md"))
            continue
        number = int(m.group(1))
        if number in numbers:
            findings.append(
                Finding("adr", Severity.ERROR, rel, f"duplicate ADR number {number:03d} ({numbers[number]})")
            )
            continue
        numbers[number] = rel
        doc = ctx.doc(rel)
        assert doc is not None
        records.append((rel, number, doc))

    if numbers:
        expected = set(range(1, max(numbers) + 1))
        for gap in sorted(expected - set(numbers)):
            findings.append(Finding("adr", Severity.ERROR, ADR_DIR, f"ADR numbering has a gap: {gap:03d} is missing"))

    for rel, number, doc in records:
        h1 = next((h for h in doc.headings if h.level == 1), None)
        if h1 is None or not h1.text.startswith(f"ADR-{number:03d}"):
            findings.append(Finding("adr", Severity.WARN, rel, f"title should start with 'ADR-{number:03d}:'",
                                    h1.line if h1 else None))
        status = _adr_status(doc)
        if status is None:
            findings.append(Finding("adr", Severity.ERROR, rel, "missing '## Status' section or status value"))
            continue
        word = status.split()[0].strip(".:*_")
        if word not in ADR_STATUSES:
            findings.append(Finding("adr", Severity.ERROR, rel,
                                    f"status '{status}' must start with one of: {', '.join(ADR_STATUSES)}"))
        elif word == "Superseded":
            ref = _ADR_REF.search(status)
            if ref is None:
                findings.append(Finding("adr", Severity.ERROR, rel, "'Superseded' must name its successor (ADR-NNN)"))
            elif int(ref.group(1)) not in numbers:
                findings.append(Finding("adr", Severity.ERROR, rel, f"successor ADR-{ref.group(1)} does not exist"))
    return findings


def check_uncertain(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    total = 0
    for rel in ctx.doc_paths():
        if rel.startswith(f"{ADR_DIR}/000"):
            continue
        doc = ctx.doc(rel)
        assert doc is not None
        count = sum(len(UNCERTAIN_RE.findall(text)) for _, text in doc.prose)
        if count:
            total += count
            findings.append(Finding("uncertain", Severity.INFO, rel, f"{count} statement(s) awaiting verification"))
    limit = ctx.cfg.max_uncertain
    if limit is not None and total > limit:
        findings.append(Finding("uncertain", ctx.soft(), ".", f"{total} uncertain markers exceed the limit of {limit}"))
    return findings


Check = Callable[[Context], list[Finding]]
CHECKS: tuple[Check, ...] = (check_structure, check_sections, check_links, check_adr, check_uncertain)


def run(cfg: Config, strict: bool = False, extra: tuple[Check, ...] = ()) -> list[Finding]:
    ctx = Context(cfg, strict)
    findings = [f for check in (*CHECKS, *extra) for f in check(ctx)]
    return sorted(findings, key=lambda f: (-f.severity, f.file, f.line or 0, f.rule))
