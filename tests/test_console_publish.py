"""Console publish flow: apply, push, open PR, and every guard (DoD 8.8-8.10). No network: a local bare repo stands
in for GitHub and a fake `gh` records what it was asked to do."""

import json
import time
from pathlib import Path

import pytest
from conftest import commit_all, git
from fastapi.testclient import TestClient

from docforge.agent.patch import make_patch
from docforge.console import publish, runs
from docforge.console.app import COOKIE, TOKEN_HEADER, ConsoleState, create_app
from docforge.init import scaffold

BASE = "http://127.0.0.1:8765"


@pytest.fixture
def world(repo: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> dict:
    scaffold(repo)
    commit_all(repo, "scaffold")
    bare = tmp_path_factory.mktemp("remote") / "demo.git"
    git(bare.parent, "init", "-q", "--bare", "-b", "main", str(bare))
    git(repo, "remote", "add", "origin", "https://github.com/acme/demo.git")
    git(repo, "config", "remote.origin.pushurl", str(bare))  # pushes go to the bare repo, never the network
    git(repo, "push", "-q", "origin", "main")

    tmp = tmp_path_factory.mktemp("agent")
    patch = tmp / "p.patch"
    patch.write_text(make_patch(repo, {"docs/API.md": "# API\n\nDocumented by the agent.\n"}), encoding="utf-8")
    script = (f'out="$1/documentation/build/agent"; mkdir -p "$out"; cp {patch} "$out/docforge.patch"; '
              'printf "## Summary\\nUpdated API docs.\\n\\n---\\nRun x: cost\\n" > "$out/report.md"; '
              'printf \'{"run_id": "abc123", "command": "impact"}\' > "$out/run.json"; '
              'echo "turn   1  \\$0.0100  stop=end_turn  out=10"')
    manager = runs.RunManager(sandbox_dir=tmp, command=lambda r, t, e: ["bash", "-c", script, "x", str(r)])

    gh_log = tmp / "gh-args.json"
    fake_gh = tmp / "gh"
    fake_gh.write_text(
        "#!/usr/bin/env python3\nimport json, sys\n"
        f"json.dump(sys.argv[1:], open({str(gh_log)!r}, 'w'))\n"
        "print('https://github.com/acme/demo/pull/7')\n", encoding="utf-8")
    fake_gh.chmod(0o755)
    monkeypatch.setenv("DOCFORGE_GH", str(fake_gh))

    state = ConsoleState(port=8765)
    client = TestClient(create_app(state, manager), base_url=BASE)
    client.cookies.set(COOKIE, state.token)
    h = {TOKEN_HEADER: state.token}
    rid = client.post("/api/repos", json={"path": str(repo)}, headers=h).json()["id"]
    return {"repo": repo, "bare": bare, "client": client, "h": h, "rid": rid, "manager": manager, "gh_log": gh_log}


def live_job(w: dict) -> str:
    client, h, rid = w["client"], w["h"], w["rid"]
    r = client.post(f"/api/repos/{rid}/runs", json={"mode": "live", "task": "impact"}, headers=h)
    job_id = r.json()["go"].rsplit("/", 1)[1]
    job = w["manager"].get(job_id)
    end = time.time() + 10
    while job.status == "running" and time.time() < end:
        time.sleep(0.02)
    assert job.status == "ok"
    return str(job_id)


def test_full_publish_flow(world: dict) -> None:
    client, h = world["client"], world["h"]
    job_id = live_job(world)
    assert "Apply patch" in client.get(f"/runs/{job_id}/review").text

    r = client.post(f"/api/runs/{job_id}/apply", headers=h)
    assert r.status_code == 200, r.text
    repo = world["repo"]
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    assert branch.startswith("docforge/impact-")
    assert git(repo, "show", "--name-only", "--format=", "HEAD").split() == ["docs/API.md"]
    page = client.get(f"/runs/{job_id}/review").text
    assert "Push branch" in page and "https://github.com/acme/demo.git" in page and "docs/API.md" in page

    r = client.post(f"/api/runs/{job_id}/push", headers=h)
    assert r.status_code == 200, r.text
    assert branch in git(world["bare"], "branch", "--list")
    page = client.get(f"/runs/{job_id}/review").text
    assert "Open pull request" in page and "Updated API docs." in page

    r = client.post(f"/api/runs/{job_id}/pr", json={"title": "docs: API", "base": "main", "body": "Updated API docs."},
                    headers=h)
    assert r.status_code == 200 and r.json()["url"] == "https://github.com/acme/demo/pull/7"
    args = json.loads(world["gh_log"].read_text())
    assert args[:2] == ["pr", "create"]
    assert args[args.index("--repo") + 1] == "acme/demo" and args[args.index("--head") + 1] == branch
    assert args[args.index("--body") + 1].endswith(publish.ATTRIBUTION)
    assert "pull/7" in client.get(f"/runs/{job_id}/review").text
    # a second PR for the same run is refused
    assert client.post(f"/api/runs/{job_id}/pr", json={"title": "again"}, headers=h).status_code == 400


def test_steps_must_happen_in_order(world: dict) -> None:
    client, h = world["client"], world["h"]
    job_id = live_job(world)
    assert "Apply the patch first" in client.post(f"/api/runs/{job_id}/push", headers=h).json()["error"]
    assert client.post(f"/api/runs/{job_id}/pr", json={"title": "x"}, headers=h).status_code == 400
    client.post(f"/api/runs/{job_id}/apply", headers=h)
    early_pr = client.post(f"/api/runs/{job_id}/pr", json={"title": "x"}, headers=h)
    assert "Push the branch first" in early_pr.json()["error"]
    assert "Already applied" in client.post(f"/api/runs/{job_id}/apply", headers=h).json()["error"]


def test_publish_actions_need_token(world: dict) -> None:
    client = world["client"]
    job_id = live_job(world)
    for step in ("apply", "push", "pr"):
        assert client.post(f"/api/runs/{job_id}/{step}", json={}).status_code == 403


def test_replays_cannot_be_published(world: dict) -> None:
    client, h = world["client"], world["h"]
    replay_mgr = world["manager"]
    replay_mgr.replay_delay = 0
    job = replay_mgr.start_replay("pilot-impact")
    time.sleep(0.2)
    r = client.post(f"/api/runs/{job.id}/apply", headers=h)
    assert r.status_code == 400 and "Replays" in r.json()["error"]


@pytest.mark.parametrize("branch", [
    "main", "master", "feature/x", "docforge/../main", "docforge/", "docforge//x", "docforge/a.lock", "docforge/./x",
    "", None,
])
def test_push_guard_rejects(branch: str | None) -> None:
    with pytest.raises(publish.PublishError):
        publish.check_branch(branch)


def test_push_args_never_force() -> None:
    args = publish.push_args("docforge/impact-abc1234")
    assert args == ["push", "origin", "refs/heads/docforge/impact-abc1234:refs/heads/docforge/impact-abc1234"]
    assert not any(a in args for a in ("-f", "--force", "--force-with-lease", "--mirror", "--all", "--delete"))


def test_pr_needs_github_remote(world: dict, tmp_path: Path) -> None:
    repo = world["repo"]
    git(repo, "remote", "set-url", "origin", str(tmp_path))
    with pytest.raises(publish.PublishError, match="GitHub"):
        publish.github_repo(repo)


def test_attribution_added_once() -> None:
    once = publish.with_attribution("Body")
    assert once.endswith(publish.ATTRIBUTION) and publish.with_attribution(once) == once
