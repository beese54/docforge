"""Agent tests. The model is always a scripted fake: nothing here calls the API or spends credit."""

import json
import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from conftest import commit_all
from typer.testing import CliRunner

from docforge.agent.budget import BudgetExceeded, BudgetGuard, read_ledger
from docforge.agent.patch import make_patch
from docforge.agent.policy import ToolError, ToolLayer
from docforge.agent.runner import AgentError, run
from docforge.cli import app
from docforge.init import scaffold

# --- fakes ----------------------------------------------------------------------------------------------


def usage(inp: int = 1000, out: int = 500) -> SimpleNamespace:
    return SimpleNamespace(input_tokens=inp, output_tokens=out, cache_read_input_tokens=0,
                           cache_creation_input_tokens=0)


def tool_call(name: str, **args: Any) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=f"tu_{name}_{len(args)}", name=name, input=args)


def reply(*blocks: SimpleNamespace, stop: str = "tool_use") -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason=stop, usage=usage())


class FakeMessages:
    def __init__(self, script: list[Any], input_tokens: int = 1000) -> None:
        self.script = list(script)
        self.input_tokens = input_tokens
        self.requests: list[dict[str, Any]] = []

    def count_tokens(self, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(input_tokens=self.input_tokens)

    @contextmanager
    def stream(self, **kwargs: Any) -> Iterator[SimpleNamespace]:
        self.requests.append(kwargs)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        yield SimpleNamespace(get_final_message=lambda: step)


class FakeClient:
    def __init__(self, script: list[Any], input_tokens: int = 1000) -> None:
        self.messages = FakeMessages(script, input_tokens)


@pytest.fixture
def project(repo: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("DOCFORGE_HOME", str(tmp_path_factory.mktemp("home")))
    scaffold(repo)
    (repo / "src").mkdir()
    (repo / "src/app.ts").write_text("export const x = 1\n")
    (repo / ".env").write_text("SECRET=hunter2\n")
    commit_all(repo, "baseline")
    return repo


def guard(per_run: float = 0.50, monthly: float = 10.0) -> BudgetGuard:
    return BudgetGuard("impact", per_run, monthly)


# --- policy enforcement point (DoD 4.1) --------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["src/app.ts", "docs/../src/app.ts", "../outside.md", "/etc/passwd.md", "C:/x.md", "docs\\API.md",
     "docs/diagram.png", ".github/workflows/docforge.yml", "docforge.toml"],
)
def test_pep_allowlist_denies(project: Path, path: str) -> None:
    tools = ToolLayer(root=project)
    with pytest.raises(ToolError, match="denied"):
        tools.write_doc(path, "x")
    assert tools.staged == {}
    assert len(tools.events) == 1 and tools.events[0].tool == "write_doc"


@pytest.mark.parametrize("path", ["docs/API.md", "docs/adr/001-x.md", "README.md", "CHANGELOG.md"])
def test_pep_allowlist_allows(project: Path, path: str) -> None:
    tools = ToolLayer(root=project)
    tools.write_doc(path, "# ok")
    assert tools.staged[path] == "# ok\n" and tools.events == []
    assert not (project / path).exists() or (project / path).read_text() != "# ok\n"  # staged, not written


def test_pep_refuses_secrets_and_escapes(project: Path) -> None:
    tools = ToolLayer(root=project)
    with pytest.raises(ToolError, match="secret"):
        tools.read_file(".env")
    assert ".env" not in tools.list_files("")
    assert "hunter2" not in tools.grep("SECRET", "**")
    os.symlink("/etc", project / "docs/escape")
    with pytest.raises(ToolError, match="outside"):
        tools.read_file("docs/escape/hostname")
    assert {e.tool for e in tools.events} == {"read_file"}


def test_read_file_sees_staged_content(project: Path) -> None:
    tools = ToolLayer(root=project)
    tools.write_doc("docs/API.md", "# new")
    assert tools.read_file("docs/API.md") == "# new\n"


# --- runner end to end with a scripted model --------------------------------------------------------------


def test_runner_produces_reviewable_patch(project: Path) -> None:
    client = FakeClient([
        reply(tool_call("write_doc", path="src/app.ts", content="hacked")),
        reply(tool_call("write_doc", path="docs/API.md", content="# API\n\n## Overview\n\nUpdated.\n")),
        reply(tool_call("finish", report="## Summary\nUpdated API docs.")),
    ])
    out = project / "out"
    result = run(client, ToolLayer(root=project, base="HEAD"), guard(), "task", out)

    assert result.files_changed == ["docs/API.md"]
    patch = (out / "docforge.patch").read_text()
    assert "b/docs/API.md" in patch and "src/app.ts" not in patch
    assert "DENY write_doc 'src/app.ts'" in (out / "policy.log").read_text()
    assert "Updated API docs" in (out / "report.md").read_text()
    assert (project / "src/app.ts").read_text() == "export const x = 1\n"  # nothing applied
    subprocess.run(["git", "apply", "--check", str(out / "docforge.patch")], cwd=project, check=True)

    # the denied write came back to the model as an error result
    second_request = client.messages.requests[1]
    denied = second_request["messages"][2]["content"][0]  # user turn answering the first tool call
    assert denied["type"] == "tool_result" and denied["is_error"] is True and "denied" in denied["content"]
    assert second_request["model"] == "claude-sonnet-5-5"
    assert second_request["output_config"] == {"effort": "medium"}
    assert "write_doc" in (out / "trace.log").read_text()


def test_patch_handles_missing_trailing_newline(project: Path) -> None:
    (project / "docs/API.md").write_text("# API\nno newline", encoding="utf-8")
    commit_all(project, "no newline")
    patch = make_patch(project, {"docs/API.md": "# API\nfixed\n", "docs/NEW.md": "# New\n"})
    (project / "p.patch").write_text(patch)
    subprocess.run(["git", "apply", "--check", "p.patch"], cwd=project, check=True)


# --- budget guard (DoD 4.2) ----------------------------------------------------------------------------------


def test_max_tokens_sized_to_budget() -> None:
    assert guard(per_run=0.50).max_tokens_for(10_000) == 32_000  # capped by MAX_OUTPUT_TOKENS
    assert guard(per_run=0.05).max_tokens_for(10_000) == 2_500  # ($0.05 - 10k * $2.50/M) / $10/M


def test_budget_guard_refuses_before_calling(project: Path) -> None:
    client = FakeClient([reply(tool_call("finish", report="x"))], input_tokens=100_000)
    out = project / "out"
    with pytest.raises(AgentError, match="budget exhausted"):
        run(client, ToolLayer(root=project), guard(per_run=0.10), "task", out)
    assert client.messages.requests == []  # the model was never called
    assert not (out / "docforge.patch").exists() and not (out / "docforge.partial.patch").exists()
    assert read_ledger()[-1].note.startswith("refused")


def test_monthly_cap_counts_previous_runs(project: Path) -> None:
    first = guard(per_run=1.0, monthly=0.02)
    first.record(usage(inp=0, out=1_500))  # $0.015
    with pytest.raises(BudgetExceeded):
        guard(per_run=1.0, monthly=0.02).max_tokens_for(0)


def test_run_spend_accumulates_across_turns(project: Path) -> None:
    client = FakeClient([reply(tool_call("list_files", directory="")), reply(tool_call("finish", report="r"))])
    g = guard()
    run(client, ToolLayer(root=project), g, "task", project / "out")
    assert g.run_spent == pytest.approx(2 * (1000 * 2e-6 + 500 * 10e-6))
    assert len([r for r in read_ledger() if r.run_id == g.run_id]) == 2


# --- API failure (DoD 4.3) -------------------------------------------------------------------------------------


def dropped() -> Exception:
    return httpx2.RemoteProtocolError("peer closed connection without sending complete message body")


def conn_error() -> Exception:
    return anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))


@pytest.fixture(autouse=True)
def instant_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    from docforge.agent import runner

    monkeypatch.setattr(runner, "RETRY_BASE_SECONDS", 0.0)


@pytest.mark.parametrize(
    "errors",
    [
        [conn_error(), conn_error(), conn_error()],  # retried STREAM_ATTEMPTS times, then fails
        [dropped(), dropped(), dropped()],
        [reply(stop="refusal")],
        [reply(stop="max_tokens")],
    ],
)
def test_failure_writes_no_patch(project: Path, errors: list[Any]) -> None:
    client = FakeClient([reply(tool_call("write_doc", path="docs/API.md", content="# finished doc")), *errors])
    out = project / "out"
    with pytest.raises(AgentError):
        run(client, ToolLayer(root=project), guard(), "task", out)
    assert not (out / "docforge.patch").exists() and not (out / "report.md").exists()
    # What was already paid for survives, under a name `docforge apply` is never pointed at by default.
    partial = (out / "docforge.partial.patch").read_text()
    assert "b/docs/API.md" in partial
    assert "FAILED" in (out / "trace.log").read_text()
    assert json.loads((out / "run.json").read_text())["status"] == "failed"


def test_dropped_stream_is_retried_and_charged_worst_case(project: Path) -> None:
    client = FakeClient([dropped(), reply(tool_call("finish", report="done"))])
    g = guard()
    result = run(client, ToolLayer(root=project), g, "task", project / "out")
    assert result.turns == 1 and len(client.messages.requests) == 2
    worst = next(r for r in read_ledger() if r.note.startswith("worst case charged"))
    assert worst.cost_usd == pytest.approx(1000 * 2.5e-6 + 32_000 * 10e-6)  # input at cache-write + full output
    assert g.run_spent == pytest.approx(worst.cost_usd + 1000 * 2e-6 + 500 * 10e-6)
    assert "stream interrupted" in (project / "out/trace.log").read_text()


def test_unexpected_error_still_saves_partial(project: Path) -> None:
    client = FakeClient([reply(tool_call("write_doc", path="docs/API.md", content="# done")), ValueError("boom")])
    with pytest.raises(ValueError):
        run(client, ToolLayer(root=project), guard(), "task", project / "out")
    assert (project / "out/docforge.partial.patch").exists()


def test_failure_without_writes_has_no_partial_patch(project: Path) -> None:
    client = FakeClient([reply(stop="refusal")])
    out = project / "out"
    with pytest.raises(AgentError):
        run(client, ToolLayer(root=project), guard(), "task", out)
    assert not (out / "docforge.partial.patch").exists() and (out / "trace.log").exists()


def test_turn_limit_depends_on_command(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from docforge.agent import runner

    monkeypatch.setitem(runner.MAX_TURNS, "adr", 2)
    client = FakeClient([reply(tool_call("list_files", directory="")) for _ in range(3)])
    with pytest.raises(AgentError, match="after 2 turns"):
        run(client, ToolLayer(root=project), BudgetGuard("adr", 0.5, 10.0), "task", project / "out")


def test_cli_without_credentials_exits_3(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(project / "nohome"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(project / "nohome"))
    result = CliRunner().invoke(app, ["agent", "impact", "--path", str(project), "--base", "HEAD"])
    assert result.exit_code == 3, result.output


def test_usage_command(project: Path) -> None:
    g = guard()
    g.record(usage())
    result = CliRunner().invoke(app, ["usage", "--last"])
    assert result.exit_code == 0 and g.run_id in result.output and "$0.0070" in result.output
