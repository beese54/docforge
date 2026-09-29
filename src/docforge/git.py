"""Thin wrappers over the git CLI. Everything else in docforge talks to git through here."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(Exception):
    """A git command failed (not a repo, unknown ref, ...)."""


def run(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout
    except FileNotFoundError as exc:
        raise GitError("git is not installed") from exc
    except subprocess.CalledProcessError as exc:
        raise GitError(exc.stderr.strip() or f"git {' '.join(args)} failed") from exc


def is_repo(root: Path) -> bool:
    try:
        return run(root, "rev-parse", "--is-inside-work-tree").strip() == "true"
    except GitError:
        return False


def resolve(root: Path, ref: str) -> str:
    return run(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").strip()


def default_base(root: Path) -> str | None:
    """Merge-base with the main branch, preferring the remote. None when there is nothing to compare with.

    On main itself the merge-base is HEAD, so only uncommitted changes are compared.
    """
    for candidate in ("origin/main", "origin/master", "main", "master"):
        try:
            return run(root, "merge-base", "HEAD", candidate).strip() or None
        except GitError:
            continue
    return None


def _has_head(root: Path) -> bool:
    try:
        resolve(root, "HEAD")
        return True
    except GitError:
        return False


@dataclass(frozen=True)
class Commit:
    sha: str
    files: tuple[str, ...]
    docs_impact: tuple[str, ...]  # values of `Docs-Impact:` trailers


_REC, _FIELD, _SEP = "\x1e", "\x1f", "\x1d"


def commits(root: Path, base: str) -> list[Commit]:
    """Non-merge commits in base..HEAD with their changed files and Docs-Impact trailers."""
    out = run(
        root, "log", "--no-merges", "--name-only", "--no-renames",
        f"--format={_REC}%H{_FIELD}%(trailers:key=Docs-Impact,valueonly,separator=%x1d){_FIELD}",
        f"{base}..HEAD",
    )
    result: list[Commit] = []
    for record in out.split(_REC)[1:]:
        sha, trailers, files = record.split(_FIELD, 2)
        result.append(
            Commit(
                sha=sha,
                files=tuple(f for f in files.splitlines() if f.strip()),
                docs_impact=tuple(t.strip() for t in trailers.split(_SEP) if t.strip()),
            )
        )
    return result


def uncommitted(root: Path) -> list[str]:
    """Staged, unstaged and untracked (not ignored) paths."""
    changed = set(run(root, "diff", "--name-only", "HEAD").splitlines()) if _has_head(root) else set()
    changed.update(run(root, "ls-files", "--others", "--exclude-standard").splitlines())
    return sorted(p for p in changed if p)


def describe(root: Path) -> str:
    return run(root, "describe", "--tags", "--always", "--dirty").strip()
