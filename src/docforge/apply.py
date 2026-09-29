"""`docforge apply`: put a reviewed agent patch on a new branch. Runs on the host; never pushes.

The same path allowlist the agent was held to is re-checked here, so a patch that was edited, or produced
by something other than the sandboxed agent, still cannot touch code.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from docforge import git, globs
from docforge.config import AGENT_WRITABLE

_DIFF_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)$")
_FILE_LINE = re.compile(r"^(?:---|\+\+\+) (?:[ab]/)?(\S+)")
_RENAME = re.compile(r"^(?:rename|copy) (?:from|to) (\S+)$")


class ApplyError(Exception):
    """The patch was refused or could not be applied. Nothing was changed."""


@dataclass(frozen=True)
class Applied:
    branch: str
    commit: str
    files: list[str]


def patch_paths(patch: str) -> set[str]:
    """Every path a patch mentions: diff headers, ---/+++ lines and rename/copy lines."""
    paths: set[str] = set()
    for line in patch.splitlines():
        for regex in (_DIFF_HEADER, _FILE_LINE, _RENAME):
            m = regex.match(line)
            if m:
                paths.update(p for p in m.groups() if p != "/dev/null")
    return paths


def disallowed(paths: set[str]) -> list[str]:
    return sorted(p for p in paths if not (globs.match_any(p, AGENT_WRITABLE) and p.lower().endswith(".md")))


def apply_patch(root: Path, patch_file: Path, branch: str | None = None) -> Applied:
    patch = patch_file.read_text(encoding="utf-8")
    paths = patch_paths(patch)
    if not paths:
        raise ApplyError("patch is empty; nothing to apply")
    bad = disallowed(paths)
    if bad:
        raise ApplyError("patch touches paths outside README.md, CHANGELOG.md and docs/**.md: " + ", ".join(bad))

    run_info = patch_file.with_name("run.json")
    meta = json.loads(run_info.read_text(encoding="utf-8")) if run_info.is_file() else {}
    task, run_id = meta.get("command", "update"), meta.get("run_id", "manual")
    short = git.run(root, "rev-parse", "--short", "HEAD").strip()
    branch = branch or f"docforge/{task}-{short}"
    if git.run(root, "branch", "--list", branch).strip():
        raise ApplyError(f"branch '{branch}' already exists")

    try:
        git.run(root, "apply", "--check", "--index", str(patch_file))
    except git.GitError as exc:
        raise ApplyError(f"patch does not apply cleanly: {exc}") from exc

    git.run(root, "checkout", "-q", "-b", branch)
    git.run(root, "apply", "--index", str(patch_file))
    files = sorted(paths)
    git.run(root, "commit", "-q", "-m", f"docs: docforge {task} (run {run_id})\n\nFiles: {', '.join(files)}",
            "--", *files)
    return Applied(branch=branch, commit=git.run(root, "rev-parse", "--short", "HEAD").strip(), files=files)
