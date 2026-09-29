import json
from pathlib import Path

import pytest
from conftest import commit_all, git
from typer.testing import CliRunner

from docforge.agent.patch import make_patch
from docforge.apply import ApplyError, apply_patch, patch_paths
from docforge.cli import app


@pytest.fixture
def project(repo: Path) -> Path:
    (repo / "docs").mkdir()
    (repo / "docs/API.md").write_text("# API\n")
    (repo / "src").mkdir()
    (repo / "src/app.ts").write_text("export const x = 1\n")
    commit_all(repo, "baseline")
    return repo


def write_patch(root: Path, text: str, command: str = "impact") -> Path:
    out = root.parent / f"{root.name}-out"
    out.mkdir(exist_ok=True)
    (out / "docforge.patch").write_text(text)
    (out / "run.json").write_text(json.dumps({"command": command, "run_id": "abc123"}))
    return out / "docforge.patch"


def test_apply_creates_branch_and_commit(project: Path) -> None:
    patch = write_patch(project, make_patch(project, {"docs/API.md": "# API\n\nNew.\n", "docs/NEW.md": "# New\n"}))
    result = apply_patch(project, patch)
    assert result.branch.startswith("docforge/impact-")
    assert git(project, "rev-parse", "--abbrev-ref", "HEAD").strip() == result.branch
    changed = git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert sorted(changed) == ["docs/API.md", "docs/NEW.md"]
    assert "run abc123" in git(project, "log", "-1", "--format=%B")


def test_apply_leaves_uncommitted_code_out_of_the_commit(project: Path) -> None:
    (project / "src/app.ts").write_text("export const x = 2\n")  # developer's work in progress
    patch = write_patch(project, make_patch(project, {"docs/API.md": "# API v2\n"}))
    apply_patch(project, patch)
    assert git(project, "show", "--name-only", "--format=", "HEAD").split() == ["docs/API.md"]
    assert "src/app.ts" in git(project, "status", "--porcelain")


@pytest.mark.parametrize(
    "patch_text",
    [
        "diff --git a/src/app.ts b/src/app.ts\n--- a/src/app.ts\n+++ b/src/app.ts\n@@ -1 +1 @@\n-x\n+y\n",
        # a doc header smuggling a code path through ---/+++ lines
        "diff --git a/docs/API.md b/docs/API.md\n--- a/docs/API.md\n+++ b/src/app.ts\n@@ -1 +1 @@\n-x\n+y\n",
        "diff --git a/docs/API.md b/docs/API.md\nrename from docs/API.md\nrename to src/evil.ts\n",
        "diff --git a/docs/run.sh b/docs/run.sh\nnew file mode 100755\n"
        "--- /dev/null\n+++ b/docs/run.sh\n@@ -0,0 +1 @@\n+x\n",
    ],
)
def test_apply_refuses(project: Path, patch_text: str) -> None:
    before = git(project, "rev-parse", "HEAD")
    with pytest.raises(ApplyError, match="outside"):
        apply_patch(project, write_patch(project, patch_text))
    assert git(project, "rev-parse", "HEAD") == before
    assert git(project, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"


def test_apply_refuses_stale_patch_without_side_effects(project: Path) -> None:
    patch = write_patch(project, make_patch(project, {"docs/API.md": "# API changed\n"}))
    (project / "docs/API.md").write_text("# Someone else edited this\n")
    commit_all(project, "concurrent edit")
    with pytest.raises(ApplyError, match="does not apply"):
        apply_patch(project, patch)
    assert git(project, "branch", "--list", "docforge/*") == ""


def test_patch_paths() -> None:
    assert patch_paths("diff --git a/docs/A.md b/docs/A.md\nnew file mode 100644\n--- /dev/null\n+++ b/docs/A.md\n") \
        == {"docs/A.md"}


def test_cli_apply_exit_codes(project: Path) -> None:
    bad = write_patch(project, "diff --git a/src/app.ts b/src/app.ts\n")
    result = CliRunner().invoke(app, ["apply", str(bad), "--path", str(project)])
    assert result.exit_code == 1 and "outside" in result.output
    good = write_patch(project, make_patch(project, {"docs/API.md": "# API!\n"}))
    ok = CliRunner().invoke(app, ["apply", str(good), "--path", str(project), "--branch", "docs/test"])
    assert ok.exit_code == 0 and "docs/test" in ok.output and "gh pr create" in ok.output
