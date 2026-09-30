"""`docforge init`: scaffold the documentation structure. Creates missing files only and never overwrites."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from string import Template

from docforge import globs, resources
from docforge.config import CONFIG_NAME
from docforge.doctypes import DOC_TYPES, render

GITIGNORE_LINE = "documentation/build/"
_SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".next", "target"}


@dataclass(frozen=True)
class Candidate:
    category: str
    docs: tuple[str, ...]
    adr_worthy: bool
    patterns: tuple[str, ...]


# Candidate impact rules. A pattern is kept only if it matches a file that exists in the repo, so the
# generated map describes this repository rather than every stack docforge knows about.
CANDIDATES: tuple[Candidate, ...] = (
    Candidate("dependencies", ("docs/DEPENDENCIES.md",), True, (
        "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "pyproject.toml", "uv.lock",
        "poetry.lock", "requirements*.txt", "go.mod", "Cargo.toml", "Gemfile", "composer.json", "pom.xml",
        "build.gradle*")),
    Candidate("deployment", ("docs/DEPLOYMENT.md", "docs/OPERATIONS.md"), True, (
        "Dockerfile", "**/Dockerfile", "**/*.Dockerfile", "docker-compose*.yml", "compose*.yaml", "init.sh", "Procfile",
        "fly.toml", "vercel.json", "netlify.toml", "**/*.tf", "k8s/**", "helm/**", "deploy/**", "infra/**")),
    Candidate("data", ("docs/DATA_MODEL.md",), True, (
        "**/migrations/**", "prisma/schema.prisma", "**/schema.sql", "**/models.py", "**/types/domain.ts")),
    Candidate("security", ("docs/SECURITY.md",), True, (
        "**/auth/**", "**/security/**", "**/sanitize.*", "**/middleware/**")),
    Candidate("api", ("docs/API.md",), False, (
        "server/**", "api/**", "**/routes/**", "openapi.*", "**/openapi.*")),
    Candidate("ci", ("docs/TESTING.md", "docs/DEPLOYMENT.md"), False, (".github/workflows/**", ".gitlab-ci.yml")),
    Candidate("testing", ("docs/TESTING.md",), False, (
        "vitest.config.*", "jest.config.*", "playwright.config.*", "pytest.ini", "conftest.py", "tox.ini")),
)


def repo_files(root: Path) -> list[str]:
    """Tracked + untracked-but-not-ignored files when in git; a pruned walk otherwise."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout
        return sorted(line for line in out.splitlines() if line)
    except (subprocess.CalledProcessError, FileNotFoundError):
        files: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            rel = Path(dirpath).relative_to(root)
            files.extend((rel / f).as_posix() for f in filenames)
        return sorted(files)


def guess_impact(files: list[str]) -> str:
    """TOML `[[impact]]` blocks for the candidate patterns that match this repository."""
    blocks: list[str] = []
    for cand in CANDIDATES:
        hits = [p for p in cand.patterns if any(globs.match(f, p) for f in files)]
        if not hits:
            continue
        blocks.append(
            "[[impact]]\n"
            f'category = "{cand.category}"\n'
            f"globs = [{', '.join(repr_toml(p) for p in hits)}]\n"
            f"docs = [{', '.join(repr_toml(d) for d in cand.docs)}]\n"
            f"adr_worthy = {'true' if cand.adr_worthy else 'false'}\n"
        )
    return "\n".join(blocks)


def repr_toml(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _plan(root: Path) -> dict[str, str]:
    """Relative path -> content for every file init may create."""
    name = root.resolve().name
    plan: dict[str, str] = {doc.path: render(doc, name) for doc in DOC_TYPES}
    plan["CHANGELOG.md"] = resources.read("CHANGELOG.md")
    plan["docs/adr/000-template.md"] = resources.read("adr-template.md")
    plan["documentation/manual.yaml"] = resources.read("manual.yaml")
    plan["documentation/templates/manual-header.tex"] = resources.read("manual-header.tex")
    plan[".github/workflows/docforge.yml"] = resources.read("docforge.yml")
    plan[CONFIG_NAME] = Template(resources.read("docforge.toml")).substitute(
        name=name, impact=guess_impact(repo_files(root))
    )
    return plan


def scaffold(root: Path) -> tuple[list[str], list[str]]:
    """Create missing files. Returns (created, skipped) relative paths."""
    created: list[str] = []
    skipped: list[str] = []
    for rel, content in _plan(root).items():
        target = root / rel
        if target.exists():
            skipped.append(rel)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as fh:  # "x": fail rather than overwrite
            fh.write(content)
        created.append(rel)

    gitignore = root / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    if GITIGNORE_LINE not in (line.strip() for line in existing):
        with gitignore.open("a", encoding="utf-8", newline="\n") as fh:
            if existing and existing[-1].strip():
                fh.write("\n")
            fh.write(f"# docforge build output\n{GITIGNORE_LINE}\n")
        created.append(".gitignore (+documentation/build/)")
    return created, skipped
