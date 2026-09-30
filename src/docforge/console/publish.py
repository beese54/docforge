"""Apply, push and open a pull request from the console, behind guards.

The console can act with the developer's GitHub login, so every step is narrow:
- Apply: exactly `docforge apply` (docs-only path re-check, new branch, no push).
- Push: only a docforge/* branch that THIS console applied, to the existing `origin`, with an explicit refspec,
  never --force, never main/master. The branch name comes from server state, never from the browser.
- Open PR: only for a branch this console pushed, with gh against the origin repository.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from docforge import git
from docforge.apply import ApplyError, apply_patch

BRANCH_RE = re.compile(r"^docforge/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$")
PROTECTED = {"main", "master"}
WINDOWS_GH = "/mnt/c/Program Files/GitHub CLI/gh.exe"
ATTRIBUTION = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"
_GITHUB_URL = re.compile(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$")


class PublishError(Exception):
    """A publish step was refused or failed; the message is shown to the user."""


@dataclass
class PublishState:
    """What the console did for one run. Only branches recorded here can be pushed or turned into PRs."""
    branch: str | None = None
    commit: str | None = None
    files: list[str] = field(default_factory=list)
    pushed: bool = False
    pr_url: str | None = None


def apply(root: Path, patch_file: Path, state: PublishState) -> PublishState:
    if state.branch:
        raise PublishError(f"Already applied on branch {state.branch}.")
    if not patch_file.is_file():
        raise PublishError("This run has no patch to apply.")
    try:
        applied = apply_patch(root, patch_file)
    except ApplyError as exc:
        raise PublishError(str(exc)) from exc
    except git.GitError as exc:
        raise PublishError(f"git: {exc}") from exc
    state.branch, state.commit, state.files = applied.branch, applied.commit, applied.files
    return state


def check_branch(branch: str | None) -> str:
    if not branch:
        raise PublishError("Apply the patch first; only branches the console created can be pushed.")
    segments = branch.split("/")
    unsafe = ".." in branch or any(s in ("", ".") or s.endswith(".lock") for s in segments)
    if branch in PROTECTED or unsafe or not BRANCH_RE.match(branch):
        raise PublishError(f"Refusing to push '{branch}': only docforge/* branches are allowed.")
    return branch


def remote_url(root: Path) -> str:
    try:
        return git.run(root, "remote", "get-url", "origin").strip()
    except git.GitError as exc:
        raise PublishError("This repository has no 'origin' remote to push to.") from exc


def push_args(branch: str) -> list[str]:
    """Explicit refspec, no force: the only shape of push the console ever runs."""
    check_branch(branch)
    return ["push", "origin", f"refs/heads/{branch}:refs/heads/{branch}"]


def outgoing(root: Path, branch: str) -> list[str]:
    """Commits on the branch that the remote's default branch does not have (for the confirm screen)."""
    base = default_base_branch(root)
    for ref in (f"origin/{base}", base):
        try:
            return git.run(root, "log", "--oneline", f"{ref}..{branch}").splitlines()
        except git.GitError:
            continue
    return git.run(root, "log", "--oneline", "-5", branch).splitlines()


def push(root: Path, state: PublishState) -> PublishState:
    branch = check_branch(state.branch)
    remote_url(root)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}  # never hang waiting for a password prompt
    proc = subprocess.run(["git", *push_args(branch)], cwd=root, capture_output=True, text=True, env=env,
                          timeout=180)
    if proc.returncode != 0:
        raise PublishError(f"git push failed: {proc.stderr.strip()[-400:]}")
    state.pushed = True
    return state


def github_repo(root: Path) -> str:
    m = _GITHUB_URL.search(remote_url(root))
    if not m:
        raise PublishError("Opening a pull request needs a GitHub 'origin' remote.")
    return f"{m.group(1)}/{m.group(2)}"


def default_base_branch(root: Path) -> str:
    try:
        ref = git.run(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD").strip()
        return ref.rsplit("/", 1)[-1]
    except git.GitError:
        for name in ("main", "master"):
            try:
                git.resolve(root, name)
                return name
            except git.GitError:
                continue
    return "main"


def gh_command() -> str:
    override = os.environ.get("DOCFORGE_GH")
    if override:
        return override
    found = shutil.which("gh")
    if found:
        return found
    if Path(WINDOWS_GH).is_file():
        return WINDOWS_GH  # WSL: reuse the Windows GitHub CLI login
    raise PublishError("GitHub CLI (gh) not found; install it or log in with `gh auth login`.")


def with_attribution(body: str) -> str:
    body = body.rstrip()
    return body if body.endswith(ATTRIBUTION) else f"{body}\n\n{ATTRIBUTION}"


def open_pr(root: Path, state: PublishState, title: str, body: str, base: str) -> PublishState:
    branch = check_branch(state.branch)
    if not state.pushed:
        raise PublishError("Push the branch first; the console opens pull requests only for branches it pushed.")
    if state.pr_url:
        raise PublishError(f"A pull request is already open: {state.pr_url}")
    if not title.strip():
        raise PublishError("The pull request needs a title.")
    cmd = [gh_command(), "pr", "create", "--repo", github_repo(root), "--head", branch,
           "--base", base.strip() or default_base_branch(root), "--title", title.strip(),
           "--body", with_attribution(body)]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    if proc.returncode != 0:
        raise PublishError(f"gh pr create failed: {(proc.stderr or proc.stdout).strip()[-400:]}")
    urls = re.findall(r"https://github\.com/\S+/pull/\d+", proc.stdout)
    state.pr_url = urls[-1] if urls else proc.stdout.strip()
    return state
