"""Path glob matching with `**` support (pathlib.PurePath.full_match only arrives in Python 3.13)."""

from __future__ import annotations

import re
from functools import lru_cache


@lru_cache(maxsize=512)
def _compile(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def match(path: str, pattern: str) -> bool:
    """True if a POSIX relative `path` matches `pattern` (`*` stays within a segment, `**` crosses them)."""
    return _compile(pattern).match(path) is not None


def match_any(path: str, patterns: tuple[str, ...] | list[str]) -> bool:
    return any(match(path, p) for p in patterns)
