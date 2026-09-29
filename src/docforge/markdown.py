"""Just enough Markdown structure for the checks: headings, anchors and links, with code excluded.

A full CommonMark parser would be more exact, but every rule here only needs headings and link targets, and a
line scanner that respects fenced code blocks and inline code spans gets those right for real-world docs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1")
_LINK = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_REF_DEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$")
_HTML_ID = re.compile(r"<a\s+(?:[^>]*?\s)?(?:id|name)=[\"']([^\"']+)[\"']", re.IGNORECASE)
_EXPLICIT_ID = re.compile(r"\s*\{#([^}\s]+)[^}]*\}\s*$")


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    line: int


@dataclass(frozen=True)
class Link:
    target: str
    line: int


@dataclass
class Document:
    headings: list[Heading] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    anchors: set[str] = field(default_factory=set)
    prose: list[tuple[int, str]] = field(default_factory=list)  # (line number, text) outside code fences

    def section_lines(self, title: str) -> list[str]:
        """Prose lines under the first H2 whose text equals `title` (case-insensitive), up to the next H1/H2."""
        start = next((h for h in self.headings if h.level == 2 and h.text.lower() == title.lower()), None)
        if start is None:
            return []
        end = next((h.line for h in self.headings if h.line > start.line and h.level <= 2), None)
        return [t for n, t in self.prose if n > start.line and (end is None or n < end)]


def slugify(text: str) -> str:
    """GitHub-style heading anchor (before duplicate suffixing)."""
    text = re.sub(r"<[^>]+>", "", text)  # inline HTML
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> their text
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def parse(source: str) -> Document:
    doc = Document()
    fence: str | None = None
    seen: dict[str, int] = {}
    for number, raw in enumerate(source.splitlines(), start=1):
        m = _FENCE.match(raw)
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            continue
        if m:
            fence = m.group(1)
            continue
        doc.prose.append((number, raw))
        line = _CODE_SPAN.sub("", raw)

        h = _HEADING.match(line)
        if h:
            text = h.group(2)
            explicit = _EXPLICIT_ID.search(text)
            if explicit:
                text = text[: explicit.start()]
                doc.anchors.add(explicit.group(1))
            doc.headings.append(Heading(len(h.group(1)), text.strip(), number))
            slug = slugify(text)
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            doc.anchors.add(slug if count == 0 else f"{slug}-{count}")

        doc.anchors.update(_HTML_ID.findall(line))
        for target in _LINK.findall(line):
            doc.links.append(Link(target, number))
        ref = _REF_DEF.match(line)
        if ref:
            doc.links.append(Link(ref.group(1), number))
    return doc
