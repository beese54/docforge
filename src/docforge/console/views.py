"""Read-only views for the console: doc coverage, ADRs, and spend. Built from the same modules the CLI uses."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from docforge import markdown
from docforge.agent.budget import month_spend, read_ledger
from docforge.checks import ADR_DIR, ADR_NAME, _adr_status
from docforge.config import DEFAULT_MONTHLY_USD
from docforge.doctypes import BY_PATH, UNCERTAIN_RE


@dataclass(frozen=True)
class DocCoverage:
    path: str
    title: str
    exists: bool
    sections_present: int
    sections_total: int
    uncertain: int
    lines: int

    @property
    def complete(self) -> bool:
        return self.exists and self.sections_present == self.sections_total


@dataclass(frozen=True)
class AdrRow:
    number: str
    title: str
    status: str
    path: str


def coverage(root: Path) -> list[DocCoverage]:
    rows: list[DocCoverage] = []
    for rel, doctype in BY_PATH.items():
        path = root / rel
        if not path.is_file():
            rows.append(DocCoverage(rel, doctype.title, False, 0, len(doctype.sections), 0, 0))
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        doc = markdown.parse(text)
        present = {h.text.lower() for h in doc.headings if h.level == 2}
        found = sum(1 for s in doctype.sections if s.lower() in present)
        uncertain = sum(len(UNCERTAIN_RE.findall(t)) for _, t in doc.prose)
        h1 = next((h.text for h in doc.headings if h.level == 1), doctype.title)
        rows.append(DocCoverage(rel, h1, True, found, len(doctype.sections), uncertain, text.count("\n")))
    return rows


def adrs(root: Path) -> list[AdrRow]:
    rows: list[AdrRow] = []
    adr_dir = root / ADR_DIR
    if not adr_dir.is_dir():
        return rows
    for path in sorted(adr_dir.glob("*.md")):
        m = ADR_NAME.match(path.name)
        if not m or path.name.startswith("000"):
            continue
        doc = markdown.parse(path.read_text(encoding="utf-8", errors="replace"))
        h1 = next((h.text for h in doc.headings if h.level == 1), path.stem)
        title = re.sub(r"^ADR-\d{3}:\s*", "", h1)
        rows.append(AdrRow(m.group(1), title, _adr_status(doc) or "(no status)", path.relative_to(root).as_posix()))
    return rows


def diff_lines(patch: str) -> list[tuple[str, str]]:
    """(css class, text) per line of a unified diff."""
    out: list[tuple[str, str]] = []
    for line in patch.splitlines():
        if line.startswith("diff --git"):
            out.append(("file", line.split(" b/", 1)[-1]))
        elif line.startswith(("--- ", "+++ ", "new file mode", "index ")):
            continue
        elif line.startswith("@@"):
            out.append(("hunk", line))
        elif line.startswith("+"):
            out.append(("add", line))
        elif line.startswith("-"):
            out.append(("del", line))
        else:
            out.append(("", line))
    return out


def patch_files(patch: str) -> list[str]:
    return [line.split(" b/", 1)[-1] for line in patch.splitlines() if line.startswith("diff --git")]


def render_report(md: str) -> str:
    """Small, safe Markdown-to-HTML for agent reports: headings, bullets, bold, code. Everything is escaped."""
    import html

    def inline(text: str) -> str:
        text = html.escape(text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)

    out: list[str] = []
    in_list = False
    for raw in md.splitlines():
        line = raw.rstrip()
        bullet = re.match(r"^\s*(?:[-*]|\d+\.)\s+(.*)", line)
        if bullet:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(bullet.group(1))}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        heading = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading:
            level = min(len(heading.group(1)) + 1, 4)
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif line.strip() == "---":
            out.append("<hr>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


@dataclass(frozen=True)
class RunRow:
    run_id: str
    ts: str
    command: str
    calls: int
    cost: float
    note: str


@dataclass(frozen=True)
class Spend:
    runs: list[RunRow]
    month: float
    total: float
    monthly_cap: float

    @property
    def month_pct(self) -> float:
        return min(100.0, 100.0 * self.month / self.monthly_cap) if self.monthly_cap else 0.0


def spend(monthly_cap: float = DEFAULT_MONTHLY_USD) -> Spend:
    records = read_ledger()
    grouped: dict[str, list[float]] = defaultdict(list)
    first: dict[str, tuple[str, str]] = {}
    notes: dict[str, str] = {}
    for r in records:
        grouped[r.run_id].append(r.cost_usd)
        first.setdefault(r.run_id, (r.ts, r.command))
        if r.note:
            notes[r.run_id] = r.note
    runs = [RunRow(rid, first[rid][0], first[rid][1], len(c), sum(c), notes.get(rid, "")) for rid, c in grouped.items()]
    runs.reverse()  # newest first
    return Spend(runs, month_spend(records), sum(r.cost_usd for r in records), monthly_cap)
