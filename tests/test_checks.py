import json
import socket
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from typer.testing import CliRunner

from docforge import checks, markdown
from docforge.cli import app
from docforge.config import load
from docforge.findings import REPORT_SCHEMA, Finding, Severity
from docforge.init import scaffold


@pytest.fixture
def scaffolded(repo: Path) -> Path:
    scaffold(repo)
    return repo


def run(root: Path, strict: bool = False) -> list[Finding]:
    return checks.run(load(root), strict=strict)


def rules(findings: list[Finding], severity: Severity | None = None) -> set[str]:
    return {f.rule for f in findings if severity is None or f.severity == severity}


def write(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8")


# --- init -> check round trip (DoD 1.4) -------------------------------------------------------------


def test_init_then_check(scaffolded: Path) -> None:
    findings = run(scaffolded)
    assert not [f for f in findings if f.severity == Severity.ERROR], findings
    assert rules(findings) == {"uncertain"}  # fresh skeletons are all uncertain, nothing else wrong


# --- structure (2.1) -----------------------------------------------------------------------------------


def test_structure(scaffolded: Path) -> None:
    (scaffolded / "docs/SECURITY.md").unlink()
    findings = run(scaffolded)
    assert any(f.rule == "structure" and f.file == "docs/SECURITY.md" and f.severity == Severity.ERROR
               for f in findings)


# --- sections --------------------------------------------------------------------------------------------


def test_sections_warn_then_error_in_strict(scaffolded: Path) -> None:
    write(scaffolded, "docs/API.md", "# API\n\n## Overview\n\n## Endpoints\n")
    assert any(f.rule == "sections" and "Errors" in f.message and f.severity == Severity.WARN
               for f in run(scaffolded))
    assert any(f.rule == "sections" and f.severity == Severity.ERROR for f in run(scaffolded, strict=True))


# --- links (2.2) -----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "link, broken",
    [
        ("[ok](SECURITY.md)", False),
        ("[ok](SECURITY.md#trust-boundaries)", False),
        ("[ok](../README.md)", False),
        ("[ok](#overview)", False),
        ("[ok](https://example.com/nothing)", False),
        ("[ok](<SECURITY.md>)", False),
        ("[bad](MISSING.md)", True),
        ("[bad](SECURITY.md#no-such-anchor)", True),
        ("[bad](#no-such-anchor)", True),
        ("[bad](security.md)", True),  # wrong case: fine on Windows, broken on GitHub
        ("[bad](../../outside.md)", True),
        ("![img](img/missing.png)", True),
    ],
)
def test_links(scaffolded: Path, link: str, broken: bool) -> None:
    write(scaffolded, "docs/DATA_MODEL.md", f"# Data Model\n\n## Overview\n\nSee {link}.\n")
    found = [f for f in run(scaffolded) if f.rule == "links"]
    assert bool(found) is broken, found
    if broken:
        assert found[0].line == 5 and found[0].severity == Severity.ERROR


def test_links_ignore_code(scaffolded: Path) -> None:
    write(scaffolded, "docs/DATA_MODEL.md", "# D\n\n`[x](nope.md)`\n\n```md\n[y](nope.md)\n```\n")
    assert "links" not in rules(run(scaffolded))


def test_duplicate_heading_anchor_suffix() -> None:
    doc = markdown.parse("# A\n## Setup\n## Setup\n## Setup {#custom}\n")
    assert {"setup", "setup-1", "custom"} <= doc.anchors


# --- ADR (2.3) -------------------------------------------------------------------------------------------


def adr(number: int, status: str, slug: str = "decision") -> tuple[str, str]:
    return f"docs/adr/{number:03d}-{slug}.md", f"# ADR-{number:03d}: Decision\n\n## Status\n\n{status}\n"


@pytest.mark.parametrize(
    "records, fragment",
    [
        ([adr(1, "Accepted"), adr(3, "Accepted")], "gap: 002"),
        ([adr(1, "Maybe")], "must start with one of"),
        ([adr(1, "Accepted"), adr(2, "Superseded")], "must name its successor"),
        ([adr(1, "Superseded by ADR-009")], "does not exist"),
        ([("docs/adr/1-bad name.md", "# x\n")], "NNN-kebab"),
        ([("docs/adr/001-no-status.md", "# ADR-001: x\n\n## Context\n")], "missing '## Status'"),
    ],
)
def test_adr_errors(scaffolded: Path, records: list[tuple[str, str]], fragment: str) -> None:
    for rel, text in records:
        write(scaffolded, rel, text)
    found = [f for f in run(scaffolded) if f.rule == "adr" and f.severity == Severity.ERROR]
    assert any(fragment in f.message for f in found), found


def test_adr_valid_chain(scaffolded: Path) -> None:
    for rel, text in (adr(1, "Superseded by ADR-002"), adr(2, "Accepted")):
        write(scaffolded, rel, text)
    assert "adr" not in rules(run(scaffolded))


# --- uncertain ------------------------------------------------------------------------------------------


def test_uncertain_limit(scaffolded: Path) -> None:
    cfg_path = scaffolded / "docforge.toml"
    cfg_path.write_text(cfg_path.read_text() + "\n[uncertain]\nmax_markers = 1\n", encoding="utf-8")
    assert any(f.rule == "uncertain" and f.severity == Severity.WARN and "exceed" in f.message
               for f in run(scaffolded))


# --- no network (2.7) ------------------------------------------------------------------------------------


def test_no_network(scaffolded: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("check attempted network access")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    write(scaffolded, "docs/API.md", "# API\n\n[ext](https://example.com)\n")
    run(scaffolded, strict=True)


# --- CLI + JSON contract (2.6) ---------------------------------------------------------------------------


def test_json_schema(scaffolded: Path) -> None:
    write(scaffolded, "docs/API.md", "# API\n\n[bad](nope.md)\n")
    result = CliRunner().invoke(app, ["check", "--path", str(scaffolded), "--format", "json"])
    assert result.exit_code == 1
    report = json.loads(result.output)
    jsonschema.validate(report, REPORT_SCHEMA)
    assert report["summary"]["error"] >= 1


def test_cli_exit_codes(scaffolded: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    ok = CliRunner().invoke(app, ["check", "--path", str(scaffolded)])
    assert ok.exit_code == 0, ok.output
    empty = tmp_path_factory.mktemp("empty")
    missing = CliRunner().invoke(app, ["check", "--path", str(empty)])
    assert missing.exit_code == 2
