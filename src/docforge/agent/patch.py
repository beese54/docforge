"""Turn staged writes into a `git apply`-compatible unified diff against the working tree."""

from __future__ import annotations

import difflib
from pathlib import Path

NO_NEWLINE = "\\ No newline at end of file\n"


def _diff(old: str, new: str, a: str, b: str) -> list[str]:
    out: list[str] = []
    for line in difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), a, b, n=3):
        # A final line without "\n" is emitted as-is by difflib; git expects the newline plus a marker line.
        out.append(line if line.endswith("\n") else line + "\n" + NO_NEWLINE)
    return out


def make_patch(root: Path, staged: dict[str, str]) -> str:
    chunks: list[str] = []
    for rel in sorted(staged):
        target = root / rel
        if target.is_file():
            old = target.read_text(encoding="utf-8")
            if old == staged[rel]:
                continue
            chunks.append(f"diff --git a/{rel} b/{rel}\n")
            chunks.extend(_diff(old, staged[rel], f"a/{rel}", f"b/{rel}"))
        else:
            chunks.append(f"diff --git a/{rel} b/{rel}\nnew file mode 100644\n")
            chunks.extend(_diff("", staged[rel], "/dev/null", f"b/{rel}"))
    return "".join(chunks)
