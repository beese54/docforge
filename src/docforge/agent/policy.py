"""The policy enforcement point: the ONLY way the agent reaches the repository.

Reads are confined to the repository and skip secrets; writes are staged in memory and allowed only on
documentation paths (config.AGENT_WRITABLE). Every denial is recorded as a policy event. Nothing here writes
to disk; the runner turns staged writes into a patch that a human reviews and applies.
"""

from __future__ import annotations

import datetime as dt
import posixpath
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docforge import git, globs
from docforge.config import AGENT_WRITABLE

MAX_READ_BYTES = 200_000
MAX_DIFF_CHARS = 150_000
MAX_GREP_RESULTS = 200
MAX_LIST = 2_000
SECRET_PATTERNS = (".env", ".env.*", "**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/id_rsa*", "**/*.p12",
                   ".git/**", "**/.npmrc", "**/.pypirc")


class ToolError(Exception):
    """The request is invalid or denied; the message goes back to the model as an error tool_result."""


@dataclass(frozen=True)
class PolicyEvent:
    ts: str
    tool: str
    path: str
    decision: str  # "deny"
    reason: str

    def line(self) -> str:
        return f"{self.ts} {self.decision.upper()} {self.tool} {self.path!r}: {self.reason}"


def _schema(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "list_files",
        "description": "List repository files (git-tracked or untracked-not-ignored) under a directory. "
        "Use \"\" for the repository root.",
        "input_schema": _schema({"directory": {"type": "string"}}),
    },
    {
        "name": "read_file",
        "description": f"Read a UTF-8 file from the repository (max {MAX_READ_BYTES} bytes, secrets refused).",
        "input_schema": _schema({"path": {"type": "string"}}),
    },
    {
        "name": "grep",
        "description": "Search repository files with a Python regular expression. `path_glob` limits the files "
        "(e.g. \"src/**/*.ts\"; \"**\" for all). Returns file:line: text.",
        "input_schema": _schema({"pattern": {"type": "string"}, "path_glob": {"type": "string"}}),
    },
    {
        "name": "git_diff",
        "description": "The code change under review: unified diff from the base ref to the working tree.",
        "input_schema": _schema({}),
    },
    {
        "name": "write_doc",
        "description": "Propose the full new content of a documentation file. Allowed paths only: "
        + ", ".join(AGENT_WRITABLE) + ". The write is staged for human review, not applied.",
        "input_schema": _schema({"path": {"type": "string"}, "content": {"type": "string"}}),
    },
    {
        "name": "finish",
        "description": "End the task with the Markdown report for the human reviewer.",
        "input_schema": _schema({"report": {"type": "string"}}),
    },
]
for _tool in TOOL_DEFS:
    _tool["strict"] = True


@dataclass
class ToolLayer:
    root: Path
    base: str | None = None
    staged: dict[str, str] = field(default_factory=dict)
    events: list[PolicyEvent] = field(default_factory=list)
    report: str | None = None

    # -- path policy -----------------------------------------------------------------------------------

    def _deny(self, tool: str, path: str, reason: str) -> ToolError:
        self.events.append(PolicyEvent(dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), tool, path, "deny",
                                       reason))
        return ToolError(f"denied: {reason}")

    def _clean(self, tool: str, path: str, *, allow_root: bool = False) -> str:
        if "\x00" in path or "\\" in path:
            raise self._deny(tool, path, "invalid characters in path")
        if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
            raise self._deny(tool, path, "absolute paths are not allowed")
        rel = posixpath.normpath(path) if path else "."
        if rel == ".." or rel.startswith("../"):
            raise self._deny(tool, path, "path leaves the repository")
        if rel == "." and not allow_root:
            raise self._deny(tool, path, "a file path is required")
        resolved = (self.root / rel).resolve()
        if resolved != self.root.resolve() and self.root.resolve() not in resolved.parents:
            raise self._deny(tool, path, "path resolves outside the repository (symlink?)")
        return "" if rel == "." else rel

    def _secret(self, rel: str) -> bool:
        return globs.match_any(rel, SECRET_PATTERNS)

    # -- tools -----------------------------------------------------------------------------------------

    def list_files(self, directory: str) -> str:
        rel = self._clean("list_files", directory, allow_root=True)
        prefix = f"{rel}/" if rel else ""
        files = [f for f in git.run(self.root, "ls-files", "--cached", "--others", "--exclude-standard").splitlines()
                 if f.startswith(prefix) and not self._secret(f)]
        more = f"\n... {len(files) - MAX_LIST} more" if len(files) > MAX_LIST else ""
        return "\n".join(files[:MAX_LIST]) + more if files else "(no files)"

    def read_file(self, path: str) -> str:
        rel = self._clean("read_file", path)
        if self._secret(rel):
            raise self._deny("read_file", path, "secret or credential file")
        if rel in self.staged:
            return self.staged[rel]
        target = self.root / rel
        if not target.is_file():
            raise ToolError(f"not a file: {rel}")
        data = target.read_bytes()
        if len(data) > MAX_READ_BYTES:
            raise ToolError(f"{rel} is {len(data)} bytes; limit is {MAX_READ_BYTES}. Use grep instead.")
        if b"\x00" in data[:8192]:
            raise ToolError(f"{rel} looks binary")
        return data.decode("utf-8", errors="replace")

    def grep(self, pattern: str, path_glob: str) -> str:
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"invalid regex: {exc}") from exc
        results: list[str] = []
        for rel in git.run(self.root, "ls-files", "--cached", "--others", "--exclude-standard").splitlines():
            if self._secret(rel) or not (path_glob in ("", "**") or globs.match(rel, path_glob)):
                continue
            path = self.root / rel
            if not path.is_file() or path.stat().st_size > MAX_READ_BYTES:
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if regex.search(line):
                    results.append(f"{rel}:{n}: {line.strip()[:300]}")
                    if len(results) >= MAX_GREP_RESULTS:
                        return "\n".join(results) + f"\n... truncated at {MAX_GREP_RESULTS} matches"
        return "\n".join(results) if results else "(no matches)"

    def git_diff(self) -> str:
        if not self.base:
            raise ToolError("no base ref for this task")
        diff = git.run(self.root, "diff", "--no-color", self.base, "--", ".", *(f":!{p}" for p in SECRET_PATTERNS))
        if len(diff) > MAX_DIFF_CHARS:
            return diff[:MAX_DIFF_CHARS] + f"\n... diff truncated at {MAX_DIFF_CHARS} characters; use read_file"
        return diff or "(no changes)"

    def write_doc(self, path: str, content: str) -> str:
        rel = self._clean("write_doc", path)
        if not globs.match_any(rel, AGENT_WRITABLE):
            raise self._deny("write_doc", path, f"only {', '.join(AGENT_WRITABLE)} may be written")
        if not rel.lower().endswith(".md"):
            raise self._deny("write_doc", path, "only Markdown files may be written")
        self.staged[rel] = content if content.endswith("\n") else content + "\n"
        return f"staged {rel} ({len(content)} chars) for human review"

    def finish(self, report: str) -> str:
        self.report = report
        return "report recorded"

    def dispatch(self, name: str, args: dict[str, Any]) -> str:
        handlers: dict[str, Callable[..., str]] = {
            "list_files": self.list_files, "read_file": self.read_file, "grep": self.grep,
            "git_diff": self.git_diff, "write_doc": self.write_doc, "finish": self.finish,
        }
        if name not in handlers:
            raise self._deny(name, "", "unknown tool")
        try:
            return handlers[name](**args)
        except TypeError as exc:
            raise ToolError(f"bad arguments for {name}: {exc}") from exc
