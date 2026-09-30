"""Console agent runs: replay engine, live runs via a stand-in script, SSE stream, review (DoD 8.6, 8.7)."""

import time
from pathlib import Path

import pytest
from conftest import commit_all
from fastapi.testclient import TestClient

from docforge.agent.budget import read_ledger
from docforge.agent.patch import make_patch
from docforge.console import runs, views
from docforge.console.app import COOKIE, TOKEN_HEADER, ConsoleState, create_app
from docforge.init import scaffold

BASE = "http://127.0.0.1:8765"


def wait(job: runs.Job, timeout: float = 10.0) -> None:
    end = time.time() + timeout
    while job.status == "running" and time.time() < end:
        time.sleep(0.02)
    assert job.status != "running", "job did not finish"


def make_client(manager: runs.RunManager) -> tuple[TestClient, ConsoleState]:
    state = ConsoleState(port=8765)
    client = TestClient(create_app(state, manager), base_url=BASE)
    client.cookies.set(COOKIE, state.token)
    return client, state


@pytest.fixture
def project(repo: Path) -> Path:
    scaffold(repo)
    commit_all(repo, "scaffold")
    return repo


def fake_agent(script: str) -> object:
    """A stand-in for run-agent.sh: the console only sees a process printing lines and leaving outputs."""
    def command(repo: Path, task: str, extra: list[str]) -> list[str]:
        return ["bash", "-c", script, "fake", str(repo), task, *extra]
    return command


# --- replay (8.6) ------------------------------------------------------------------------------------------------


def test_replays_are_bundled() -> None:
    names = {r.name for r in runs.replays()}
    assert names == {"pilot-impact", "pilot-bootstrap", "docforge-bootstrap"}
    boot = next(r for r in runs.replays() if r.name == "pilot-bootstrap")
    assert boot.turns == 28 and len(boot.files) == 22


@pytest.mark.parametrize("name", ["pilot-impact", "pilot-bootstrap", "docforge-bootstrap"])
def test_replay_end_to_end_costs_nothing(name: str) -> None:
    manager = runs.RunManager(replay_delay=0)
    client, state = make_client(manager)
    before = len(read_ledger())
    r = client.post(f"/api/replays/{name}", headers={TOKEN_HEADER: state.token})
    job_id = r.json()["go"].rsplit("/", 1)[1]
    job = manager.get(job_id)
    assert job is not None
    wait(job)
    assert job.status == "ok" and job.mode == "replay"
    stream = client.get(f"/api/runs/{job_id}/stream").text
    assert "event: line" in stream and "event: done" in stream and "turn" in stream
    review = client.get(f"/runs/{job_id}/review").text
    assert "This is a recorded run" in review and 'class="file"' in review
    assert len(read_ledger()) == before  # replays never spend


def test_replay_via_repo_run_form(project: Path) -> None:
    manager = runs.RunManager(replay_delay=0)
    client, state = make_client(manager)
    rid = client.post("/api/repos", json={"path": str(project)}, headers={TOKEN_HEADER: state.token}).json()["id"]
    assert "Replay a recorded run" in client.get(f"/repos/{rid}/run").text
    r = client.post(f"/api/repos/{rid}/runs", json={"mode": "replay", "replay": "pilot-impact"},
                    headers={TOKEN_HEADER: state.token})
    assert r.status_code == 200 and r.json()["go"].startswith("/runs/")


def test_replay_start_needs_token() -> None:
    client, _ = make_client(runs.RunManager(replay_delay=0))
    assert client.post("/api/replays/pilot-impact").status_code == 403


# --- live (8.7) --------------------------------------------------------------------------------------------------


LIVE_OK = r'''
repo="$1"; out="$repo/documentation/build/agent"; mkdir -p "$out"
echo "Created sandbox: dfa-test"
echo "turn   1  \$0.0100  stop=tool_use  out=50"
echo "           read_file  README.md"
echo "turn   2  \$0.0200  stop=tool_use  out=90"
echo "           write_doc  docs/API.md (20 chars)"
cp "$DOCFORGE_TEST_PATCH" "$out/docforge.patch"
printf '## Summary\nUpdated **API** docs. <script>alert(1)</script>\n' > "$out/report.md"
: > "$out/policy.log"
echo "sandbox exit: 0"
'''


def test_live_run_streams_and_reviews(project: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    patch = tmp_path / "p.patch"
    patch.write_text(make_patch(project, {"docs/API.md": "# API\n\nNew.\n"}), encoding="utf-8")
    monkeypatch.setenv("DOCFORGE_TEST_PATCH", str(patch))
    manager = runs.RunManager(sandbox_dir=tmp_path, command=fake_agent(LIVE_OK))  # type: ignore[arg-type]
    client, state = make_client(manager)
    rid = client.post("/api/repos", json={"path": str(project)}, headers={TOKEN_HEADER: state.token}).json()["id"]
    r = client.post(f"/api/repos/{rid}/runs", json={"mode": "live", "task": "impact"},
                    headers={TOKEN_HEADER: state.token})
    job = manager.get(r.json()["go"].rsplit("/", 1)[1])
    assert job is not None
    wait(job)
    assert job.status == "ok" and job.cost == pytest.approx(0.03)
    assert any(line["kind"] == "turn" for line in job.lines)
    review = client.get(f"/runs/{job.id}/review").text
    assert "docs/API.md" in review and "Updated <b>API</b> docs" in review
    assert "<script>alert(1)</script>" not in review  # agent-written report is escaped


def test_live_failure_shows_no_patch(project: Path, tmp_path: Path) -> None:
    script = 'echo "turn   1  \\$0.0100  stop=max_tokens  out=10"; echo "error: budget exhausted" >&2; exit 3'
    manager = runs.RunManager(sandbox_dir=tmp_path, command=fake_agent(script))  # type: ignore[arg-type]
    client, state = make_client(manager)
    job = manager.start_live("x", project, "impact", [], "impact on test")
    wait(job)
    assert job.status == "failed" and job.exit_code == 3
    assert any("budget exhausted" in line["text"] for line in job.lines)
    assert "No patch to apply" in client.get(f"/runs/{job.id}/review").text


def test_only_one_live_run_at_a_time(project: Path, tmp_path: Path) -> None:
    manager = runs.RunManager(sandbox_dir=tmp_path, command=fake_agent("sleep 2"))  # type: ignore[arg-type]
    first = manager.start_live("x", project, "impact", [], "first")
    with pytest.raises(runs.BusyError):
        manager.start_live("x", project, "impact", [], "second")
    wait(first)


def test_live_rejects_unknown_task_and_adr_without_title(project: Path, tmp_path: Path) -> None:
    manager = runs.RunManager(sandbox_dir=tmp_path, command=fake_agent("true"))  # type: ignore[arg-type]
    client, state = make_client(manager)
    rid = client.post("/api/repos", json={"path": str(project)}, headers={TOKEN_HEADER: state.token}).json()["id"]
    h = {TOKEN_HEADER: state.token}
    assert client.post(f"/api/repos/{rid}/runs", json={"mode": "live", "task": "rm -rf"}, headers=h).status_code == 400
    assert client.post(f"/api/repos/{rid}/runs", json={"mode": "live", "task": "adr"}, headers=h).status_code == 400


def test_report_renderer_escapes_html() -> None:
    html = views.render_report("# Title\n- item with `code` and <img src=x onerror=alert(1)>\n")
    assert "<h2>Title</h2>" in html and "<code>code</code>" in html and "<img" not in html
