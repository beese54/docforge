import hashlib
import tomllib
from pathlib import Path

from conftest import commit_all, git
from typer.testing import CliRunner

from docforge.cli import app
from docforge.config import DEFAULT_DOCS, load
from docforge.init import guess_impact, scaffold

EXPECTED = set(DEFAULT_DOCS) | {
    "docs/adr/000-template.md",
    "documentation/manual.yaml",
    "documentation/templates/manual-header.tex",
    ".github/workflows/docforge.yml",
    "docforge.toml",
}


def test_init_creates(repo: Path) -> None:
    created, skipped = scaffold(repo)
    assert set(created) >= EXPECTED
    assert skipped == []
    for rel in EXPECTED:
        assert (repo / rel).is_file(), rel
    assert "documentation/build/" in (repo / ".gitignore").read_text()
    assert load(repo).name == repo.name


def test_init_idempotent(repo: Path) -> None:
    scaffold(repo)
    commit_all(repo, "scaffold")
    created, skipped = scaffold(repo)
    assert created == []
    assert set(skipped) >= EXPECTED
    assert git(repo, "status", "--porcelain") == ""


def test_init_no_overwrite(repo: Path) -> None:
    readme = repo / "README.md"
    readme.write_text("# Mine\n\nHand-written.\n", encoding="utf-8")
    before = hashlib.sha256(readme.read_bytes()).hexdigest()
    created, skipped = scaffold(repo)
    assert "README.md" in skipped and "README.md" not in created
    assert hashlib.sha256(readme.read_bytes()).hexdigest() == before


def test_init_appends_to_existing_gitignore(repo: Path) -> None:
    (repo / ".gitignore").write_text("node_modules/", encoding="utf-8")
    scaffold(repo)
    lines = (repo / ".gitignore").read_text().splitlines()
    assert lines[0] == "node_modules/" and "documentation/build/" in lines


def test_guess_impact_matches_only_existing_files() -> None:
    files = ["package.json", "Dockerfile", "server/index.ts", "src/pipeline/sanitize.ts", "README.md"]
    toml = tomllib.loads(guess_impact(files))
    by_cat = {r["category"]: r for r in toml["impact"]}
    assert set(by_cat) == {"dependencies", "deployment", "security", "api"}
    assert by_cat["dependencies"]["globs"] == ["package.json"]
    assert by_cat["security"]["adr_worthy"] is True and by_cat["api"]["adr_worthy"] is False


def test_guess_impact_empty_repo() -> None:
    assert guess_impact([]) == ""


def test_cli_init(repo: Path) -> None:
    result = CliRunner().invoke(app, ["init", "--path", str(repo)])
    assert result.exit_code == 0, result.output
    assert "created" in result.output
    again = CliRunner().invoke(app, ["init", "--path", str(repo)])
    assert "Nothing to do" in again.output
