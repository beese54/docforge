from pathlib import Path

import pytest
from conftest import commit_all, git
from typer.testing import CliRunner

from docforge import checks, drift
from docforge.cli import app
from docforge.config import load
from docforge.findings import Finding, Severity
from docforge.init import scaffold

IMPACT = """
[[impact]]
category = "dependencies"
globs = ["package.json"]
docs = ["docs/DEPENDENCIES.md"]
adr_worthy = true

[[impact]]
category = "api"
globs = ["server/**"]
docs = ["docs/API.md"]
adr_worthy = false
"""


@pytest.fixture
def base_repo(repo: Path) -> tuple[Path, str]:
    """Scaffolded repo with an impact map and one baseline commit; returns (root, base sha)."""
    scaffold(repo)
    cfg = repo / "docforge.toml"
    cfg.write_text(cfg.read_text() + IMPACT, encoding="utf-8")
    (repo / "package.json").write_text('{"dependencies": {}}\n')
    (repo / "server").mkdir()
    (repo / "server/index.ts").write_text("export {}\n")
    return repo, commit_all(repo, "baseline")


def drift_findings(root: Path, base: str, strict: bool = False) -> list[Finding]:
    return [f for f in checks.run(load(root), strict=strict, extra=(drift.make_check(base),)) if f.rule == "drift"]


def change(root: Path, rel: str, text: str = "changed\n") -> None:
    (root / rel).write_text(text, encoding="utf-8")


def test_drift_warns_and_errors_in_strict(base_repo: tuple[Path, str]) -> None:
    root, base = base_repo
    change(root, "package.json", '{"dependencies": {"left-pad": "1"}}\n')
    commit_all(root, "add dependency")
    [finding] = drift_findings(root, base)
    assert finding.severity == Severity.WARN and finding.category == "dependencies"
    assert "docs/DEPENDENCIES.md" in finding.message
    [strict] = drift_findings(root, base, strict=True)
    assert strict.severity == Severity.ERROR


def test_non_adr_category_stays_warning_in_strict(base_repo: tuple[Path, str]) -> None:
    root, base = base_repo
    change(root, "server/index.ts")
    commit_all(root, "api change")
    [finding] = drift_findings(root, base, strict=True)
    assert finding.severity == Severity.WARN and finding.category == "api"


def test_doc_update_satisfies_drift(base_repo: tuple[Path, str]) -> None:
    root, base = base_repo
    change(root, "package.json")
    commit_all(root, "dep")
    change(root, "docs/DEPENDENCIES.md", "# Dependencies\n\n## Critical Dependencies\n\nleft-pad\n")
    commit_all(root, "docs")
    assert drift_findings(root, base, strict=True) == []


def test_uncommitted_changes_count(base_repo: tuple[Path, str]) -> None:
    root, base = base_repo
    change(root, "package.json")  # not committed
    assert [f.category for f in drift_findings(root, base)] == ["dependencies"]


def test_drift_override(base_repo: tuple[Path, str]) -> None:
    root, base = base_repo
    change(root, "package.json")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "bump lockfile\n\nDocs-Impact: none — patch release, no behaviour change")
    assert drift_findings(root, base, strict=True) == []


def test_drift_override_requires_reason(base_repo: tuple[Path, str]) -> None:
    root, base = base_repo
    change(root, "package.json")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "bump\n\nDocs-Impact: none")
    found = drift_findings(root, base, strict=True)
    assert any("no reason" in f.message for f in found)
    assert any(f.category == "dependencies" and f.severity == Severity.ERROR for f in found)


def test_override_only_covers_its_own_commit(base_repo: tuple[Path, str]) -> None:
    root, base = base_repo
    change(root, "package.json", "a\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "one\n\nDocs-Impact: none - trivial")
    change(root, "package.json", "b\n")
    commit_all(root, "two, no trailer")
    assert [f.category for f in drift_findings(root, base)] == ["dependencies"]


def test_unknown_base_is_error(base_repo: tuple[Path, str]) -> None:
    root, _ = base_repo
    [finding] = drift_findings(root, "no-such-ref")
    assert finding.severity == Severity.ERROR and "not found" in finding.message


def test_default_base_on_feature_branch(base_repo: tuple[Path, str]) -> None:
    root, _ = base_repo
    git(root, "checkout", "-q", "-b", "feature")
    change(root, "package.json")
    commit_all(root, "dep on branch")
    result = CliRunner().invoke(app, ["check", "--path", str(root), "--strict"])
    assert result.exit_code == 1 and "dependencies changed" in result.output
