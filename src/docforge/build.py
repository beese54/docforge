"""`docforge build`: Markdown -> pandoc (+ docforge.lua) -> LaTeX -> PDF manual, versioned from git."""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from docforge import git, resources
from docforge.config import Config

REPO_DEFAULTS = "documentation/manual.yaml"
REPO_HEADER = "documentation/templates/manual-header.tex"
DEFAULT_OUT = "documentation/build"
MERMAID_FAILED = "DOCFORGE-MERMAID-FAILED"
REQUIRED_TOOLS = {"pandoc": "apt install pandoc", "tectonic": "https://tectonic-typesetting.github.io"}
_LATEX_SPECIAL = {c: "\\" + c for c in "&%$#_{}"} | {"~": r"\textasciitilde{}", "^": r"\^{}", "\\": r"\textbackslash{}"}


class BuildError(Exception):
    """The manual could not be built. `code` is the CLI exit code (2 = environment, 1 = content)."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Version:
    describe: str
    date: str
    sha: str


@dataclass
class BuildResult:
    output: Path
    version: Version
    chapters: list[str]
    warnings: list[str] = field(default_factory=list)


def latex_escape(text: str) -> str:
    return "".join(_LATEX_SPECIAL.get(c, c) for c in text)


def version_of(root: Path) -> Version:
    try:
        describe = git.describe(root)
        date = git.run(root, "log", "-1", "--format=%cs").strip()
        sha = git.run(root, "rev-parse", "--short", "HEAD").strip()
        return Version(describe, date, sha)
    except git.GitError:
        return Version("unversioned", dt.date.today().isoformat(), "no-git")


def expand_chapters(cfg: Config) -> tuple[list[str], list[str]]:
    """Chapter paths in manual order (globs expanded, sorted) plus warnings for entries that match nothing."""
    chapters: list[str] = []
    warnings: list[str] = []
    for entry in cfg.manual_chapters:
        if any(ch in entry for ch in "*?["):
            matches = sorted(
                p.relative_to(cfg.root).as_posix()
                for p in cfg.root.glob(entry)
                if p.is_file() and not p.name.startswith("000")  # 000-* is the ADR template
            )
        else:
            matches = [entry] if (cfg.root / entry).is_file() else []
        if not matches:
            warnings.append(f"manual chapter not found, skipped: {entry}")
        chapters.extend(m for m in matches if m not in chapters)
    return chapters, warnings


def _repo_or_default(root: Path, rel: str, packaged: str) -> str:
    path = root / rel
    return path.read_text(encoding="utf-8") if path.is_file() else resources.read(packaged)


def build(cfg: Config, out_dir: Path | None = None, fmt: str = "pdf", strict: bool = False) -> BuildResult:
    missing = [f"{tool} ({hint})" for tool, hint in REQUIRED_TOOLS.items() if shutil.which(tool) is None]
    if fmt == "tex":
        missing = [m for m in missing if not m.startswith("tectonic")]
    if missing:
        raise BuildError("missing tools: " + ", ".join(missing), code=2)

    chapters, warnings = expand_chapters(cfg)
    if not chapters:
        raise BuildError("no manual chapters found (check [manual] chapters in docforge.toml)", code=2)
    if shutil.which("mmdc") is None:
        warnings.append("mmdc not found: Mermaid diagrams stay as code blocks")

    version = version_of(cfg.root)
    out_dir = out_dir or cfg.root / DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{cfg.name}-manual-{version.describe}").strip("-")
    output = out_dir / f"{slug}.{fmt}"

    with tempfile.TemporaryDirectory(prefix="docforge-") as tmp:
        tmpdir = Path(tmp)
        header = _repo_or_default(cfg.root, REPO_HEADER, "manual-header.tex")
        for token, value in {
            "TITLE": cfg.manual_title, "VERSION": version.describe, "DATE": version.date, "SHA": version.sha,
        }.items():
            header = header.replace(f"@@{token}@@", latex_escape(value))
        (tmpdir / "header.tex").write_text(header, encoding="utf-8")
        (tmpdir / "defaults.yaml").write_text(
            _repo_or_default(cfg.root, REPO_DEFAULTS, "manual.yaml"), encoding="utf-8"
        )
        (tmpdir / "docforge.lua").write_text(resources.read("docforge.lua"), encoding="utf-8")
        # JSON is valid YAML, and it keeps a one-file list a list (repeated -M flags would not).
        (tmpdir / "meta.yaml").write_text(
            json.dumps({
                "title": cfg.manual_title,
                "subtitle": f"Version {version.describe}",
                "date": version.date,
                "docforge-files": chapters,
                "docforge-tmp": str(tmpdir),
            }),
            encoding="utf-8",
        )
        cmd = [
            "pandoc", "--defaults", str(tmpdir / "defaults.yaml"),
            "--metadata-file", str(tmpdir / "meta.yaml"),
            "--include-in-header", str(tmpdir / "header.tex"),
            "--lua-filter", str(tmpdir / "docforge.lua"),
            "--resource-path", str(cfg.root),
            "--standalone", "-o", str(output), *chapters,
        ]
        proc = subprocess.run(cmd, cwd=cfg.root, capture_output=True, text=True)

    failed_diagrams = [line for line in proc.stderr.splitlines() if line.startswith(MERMAID_FAILED)]
    warnings.extend(failed_diagrams)
    if proc.returncode != 0:
        # tectonic prints one "note: downloading ..." per file; the actual error is in the other lines.
        meaningful = [line for line in proc.stderr.strip().splitlines() if not line.startswith("note:")]
        tail = "\n".join(meaningful[-15:])
        raise BuildError(f"pandoc failed (exit {proc.returncode}):\n{tail}")
    if strict and failed_diagrams:
        details = "\n".join(line[:500] for line in failed_diagrams)
        raise BuildError(f"{len(failed_diagrams)} Mermaid diagram(s) failed to render (--strict):\n{details}")
    return BuildResult(output=output, version=version, chapters=chapters, warnings=warnings)
