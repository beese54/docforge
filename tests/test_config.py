from pathlib import Path
from typing import Any

import jsonschema
import pytest

from docforge import globs
from docforge.config import DEFAULT_DOCS, ConfigError, load, parse
from docforge.findings import FINDING_SCHEMA, Finding, Severity

MINIMAL: dict[str, Any] = {"project": {"name": "demo"}}


def test_defaults_applied() -> None:
    cfg = parse(MINIMAL, Path("."))
    assert cfg.required_docs == DEFAULT_DOCS
    assert cfg.manual_chapters == DEFAULT_DOCS
    assert cfg.manual_title == "demo Technical Manual"
    assert cfg.budget.per_run_usd["impact"] == 0.50
    assert cfg.impact == ()


def test_full_config(tmp_path: Path) -> None:
    (tmp_path / "docforge.toml").write_text(
        """
[project]
name = "pilot"
[[impact]]
category = "dependencies"
globs = ["package.json"]
docs = ["docs/DEPENDENCIES.md"]
adr_worthy = true
[budget]
monthly_usd = 5
[budget.per_run_usd]
impact = 0.25
[uncertain]
max_markers = 3
""",
        encoding="utf-8",
    )
    cfg = load(tmp_path)
    assert cfg.impact[0].adr_worthy is True
    assert cfg.budget.monthly_usd == 5.0
    assert cfg.budget.per_run_usd == {"impact": 0.25, "adr": 0.30, "bootstrap": 3.00}
    assert cfg.max_uncertain == 3


def _rule(category: str) -> dict[str, Any]:
    return {"category": category, "globs": ["g"], "docs": ["d"]}


@pytest.mark.parametrize(
    "data, fragment",
    [
        ({}, "name is required"),
        ({"project": {"name": "x"}, "extra": 1}, "unknown key"),
        ({"project": {"name": "x", "typo": 1}}, "unknown key"),
        ({"project": {"name": "x"}, "impact": [_rule("a") | {"globs": []}]}, "globs"),
        ({"project": {"name": "x"}, "impact": [_rule("a"), _rule("a")]}, "duplicate"),
        ({"project": {"name": "x"}, "impact": [_rule("a") | {"adr_worthy": "yes"}]}, "true/false"),
        ({"project": {"name": "x"}, "budget": {"monthly_usd": 0}}, "positive"),
        ({"project": {"name": "x"}, "budget": {"per_run_usd": {"impact": True}}}, "positive"),
        ({"project": {"name": "x"}, "uncertain": {"max_markers": -1}}, "non-negative"),
    ],
)
def test_invalid(data: dict[str, Any], fragment: str) -> None:
    with pytest.raises(ConfigError, match=fragment):
        parse(data, Path("."))


def test_missing_and_malformed(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load(tmp_path)
    (tmp_path / "docforge.toml").write_text("[project\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load(tmp_path)


@pytest.mark.parametrize(
    "path, pattern, expected",
    [
        ("docs/API.md", "docs/**", True),
        ("docs/adr/001-x.md", "docs/**", True),
        ("README.md", "docs/**", False),
        ("server/pdf.ts", "server/**", True),
        ("src/a/b/c.ts", "src/**/*.ts", True),
        ("src/c.ts", "src/**/*.ts", True),
        ("src/c.tsx", "src/*.ts", False),
        ("src/a/c.ts", "src/*.ts", False),
        ("package.json", "package.json", True),
        ("sub/package.json", "package.json", False),
    ],
)
def test_globs(path: str, pattern: str, expected: bool) -> None:
    assert globs.match(path, pattern) is expected


def test_finding_serialises_to_schema() -> None:
    f = Finding(rule="links", severity=Severity.ERROR, file="docs/API.md", message="broken", line=3)
    jsonschema.validate(f.to_dict(), FINDING_SCHEMA)
    assert f.to_dict()["severity"] == "error"
    assert "docs/API.md:3" in f.to_text()


def test_schema_rejects_bad_severity() -> None:
    bad = Finding(rule="x", severity=Severity.INFO, file="f", message="m").to_dict() | {"severity": "fatal"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, FINDING_SCHEMA)
