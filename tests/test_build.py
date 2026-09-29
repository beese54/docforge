import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import commit_all, git
from typer.testing import CliRunner

from docforge.build import BuildError, build, expand_chapters, latex_escape
from docforge.cli import app
from docforge.config import load

HAVE_TOOLS = all(shutil.which(t) for t in ("pandoc", "tectonic", "mmdc", "pdftotext"))
needs_tools = pytest.mark.skipif(not HAVE_TOOLS, reason="pandoc/tectonic/mmdc/pdftotext not installed")

CONFIG = """
[project]
name = "fixture"
manual_title = "Fixture & Co Manual"

[docs]
required = ["README.md", "docs/ARCHITECTURE.md"]

[manual]
chapters = ["README.md", "docs/ARCHITECTURE.md", "docs/adr/[0-9]*.md", "docs/MISSING.md"]
"""

README = """# Introduction

## Scope

The system is described in [Architecture](docs/ARCHITECTURE.md) and its
[information flow](docs/ARCHITECTURE.md#information-flow). Licence: [LICENSE](LICENSE).
"""

ARCHITECTURE = """# Architecture

## Overview

Back to the [scope](../README.md#scope).

## Information Flow

```mermaid
%% caption: Request flow
flowchart LR
  User --> API --> Database
```

| Component | Role |
|---|---|
| API | Serves requests |
"""

ADR = "# ADR-001: Use pandoc\n\n## Status\n\nAccepted\n"


@pytest.fixture
def fixture_repo(repo: Path) -> Path:
    (repo / "docs/adr").mkdir(parents=True)
    (repo / "docforge.toml").write_text(CONFIG, encoding="utf-8")
    (repo / "README.md").write_text(README, encoding="utf-8")
    (repo / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (repo / "docs/ARCHITECTURE.md").write_text(ARCHITECTURE, encoding="utf-8")
    (repo / "docs/adr/001-use-pandoc.md").write_text(ADR, encoding="utf-8")
    (repo / "docs/adr/000-template.md").write_text("# ADR-000: template\n", encoding="utf-8")
    commit_all(repo, "docs")
    git(repo, "tag", "v1.2.0")
    return repo


def pdf_text(pdf: Path) -> str:
    return subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True).stdout


def test_expand_chapters(fixture_repo: Path) -> None:
    chapters, warnings = expand_chapters(load(fixture_repo))
    assert chapters == ["README.md", "docs/ARCHITECTURE.md", "docs/adr/001-use-pandoc.md"]
    assert warnings == ["manual chapter not found, skipped: docs/MISSING.md"]


def test_latex_escape() -> None:
    assert latex_escape("R&D 100% #1 a_b") == r"R\&D 100\% \#1 a\_b"


@needs_tools
def test_build_pdf(fixture_repo: Path) -> None:
    result = build(load(fixture_repo), strict=True)
    assert result.output.name == "fixture-manual-v1.2.0.pdf"
    info = subprocess.run(["pdfinfo", str(result.output)], capture_output=True, text=True, check=True).stdout
    assert int(re.search(r"Pages:\s+(\d+)", info).group(1)) >= 1  # type: ignore[union-attr]  # DoD 3.1

    text = pdf_text(result.output)
    assert "Contents" in text  # DoD 3.2
    assert re.search(r"1\s+Introduction", text)
    assert "v1.2.0" in text and git(fixture_repo, "describe", "--tags", "--always", "--dirty").strip() in text
    assert "Fixture & Co Manual" in text
    assert re.search(r"Figure \d+(\.\d+)?: Request flow", text)  # DoD 3.3
    assert "??" not in text  # DoD 3.4
    assert "ADR-001" in text and "ADR-000" not in text


@needs_tools
def test_cross_file_links_resolve_inside_pdf(fixture_repo: Path) -> None:
    result = build(load(fixture_repo), fmt="tex")
    tex = result.output.read_text(encoding="utf-8")
    # README -> ARCHITECTURE and ARCHITECTURE -> README (the ../ case pandoc does not rewrite) are internal links.
    for target in ("docs__architecturemd__information-flow", "readmemd__scope", "docs__architecturemd"):
        assert rf"\hyperlink{{{target}}}" in tex
        assert rf"\label{{{target}}}" in tex or rf"\hypertarget{{{target}}}" in tex  # the target exists
    # A link to a non-manual file becomes plain text, not a dead hyperlink.
    assert "LICENSE" in tex and not re.search(r"\\(href|hyperlink)\{[^}]*LICENSE", tex)


@needs_tools
def test_mermaid_failure_is_strict_error(fixture_repo: Path) -> None:
    arch = fixture_repo / "docs/ARCHITECTURE.md"
    arch.write_text(arch.read_text().replace("flowchart LR", "this is not mermaid ((("), encoding="utf-8")
    lenient = build(load(fixture_repo), fmt="tex")
    assert any("DOCFORGE-MERMAID-FAILED" in w for w in lenient.warnings)
    with pytest.raises(BuildError, match="Mermaid"):
        build(load(fixture_repo), fmt="tex", strict=True)


def test_missing_tool_exit_code(fixture_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    result = CliRunner().invoke(app, ["build", "--path", str(fixture_repo)])
    assert result.exit_code == 2 and "missing tools" in result.output
