"""docforge Console: security middleware, registry, and the Repos screen (DoD 8.1-8.4)."""

import json
from pathlib import Path

import pytest
from conftest import commit_all
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from docforge.cli import app as cli_app
from docforge.console import health, registry
from docforge.console.app import COOKIE, TOKEN_HEADER, ConsoleState, create_app
from docforge.init import scaffold

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"


@pytest.fixture
def state() -> ConsoleState:
    return ConsoleState(port=PORT)


@pytest.fixture
def client(state: ConsoleState) -> TestClient:
    c = TestClient(create_app(state), base_url=BASE)
    c.cookies.set(COOKIE, state.token)
    return c


@pytest.fixture
def project(repo: Path) -> Path:
    scaffold(repo)
    commit_all(repo, "scaffold")
    return repo


def hdr(state: ConsoleState) -> dict[str, str]:
    return {TOKEN_HEADER: state.token}


# --- 8.1 serve binds localhost only -------------------------------------------------------------------------


def test_serve_bind_is_localhost_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kw: calls.update(kw))
    result = CliRunner().invoke(cli_app, ["serve", "--port", "9999"])
    assert result.exit_code == 0, result.output
    assert calls["host"] == "127.0.0.1" and calls["port"] == 9999
    assert "http://127.0.0.1:9999/auth?t=" in result.output


def test_serve_has_no_host_option() -> None:
    result = CliRunner().invoke(cli_app, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code != 0


# --- 8.2 Host check (DNS rebinding) ---------------------------------------------------------------------------


@pytest.mark.parametrize("host", ["evil.example.com", "127.0.0.1:9999", "0.0.0.0:8765", "localhost"])
def test_host_check_rejects(client: TestClient, host: str) -> None:
    assert client.get("/", headers={"host": host}).status_code == 403


def test_host_check_accepts_localhost(client: TestClient) -> None:
    assert client.get("/", headers={"host": f"localhost:{PORT}"}).status_code == 200


# --- 8.3 session cookie + action token (CSRF) ------------------------------------------------------------------


def test_pages_need_session(state: ConsoleState) -> None:
    anon = TestClient(create_app(state), base_url=BASE)
    r = anon.get("/")
    assert r.status_code == 401 and "Session needed" in r.text
    assert state.token not in r.text  # the token is never shown without a session


def test_auth_link_sets_strict_httponly_cookie(state: ConsoleState) -> None:
    anon = TestClient(create_app(state), base_url=BASE, follow_redirects=False)
    assert anon.get("/auth?t=wrong").status_code == 401
    r = anon.get(f"/auth?t={state.token}")
    assert r.status_code == 303
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


@pytest.mark.parametrize("headers", [{}, {TOKEN_HEADER: "wrong"}])
def test_csrf_actions_need_token(client: TestClient, project: Path, headers: dict[str, str]) -> None:
    r = client.post("/api/repos", json={"path": str(project)}, headers=headers)
    assert r.status_code == 403
    assert registry.load() == []


def test_csrf_cookie_alone_is_not_enough(state: ConsoleState, project: Path) -> None:
    # A cross-site form post could carry the cookie only if SameSite failed; without the header it still fails.
    c = TestClient(create_app(state), base_url=BASE)
    c.cookies.set(COOKIE, state.token)
    assert c.post("/api/repos", json={"path": str(project)}).status_code == 403


# --- registry + Repos screen (8.4) ------------------------------------------------------------------------------


def test_add_list_remove_repo(client: TestClient, state: ConsoleState, project: Path) -> None:
    r = client.post("/api/repos", json={"path": str(project)}, headers=hdr(state))
    assert r.status_code == 200
    rid = r.json()["id"]
    page = client.get("/")
    assert project.name in page.text and "Healthy" in page.text
    assert client.post(f"/api/repos/{rid}/remove", headers=hdr(state)).status_code == 200
    assert registry.load() == []


@pytest.mark.parametrize("bad", ["/definitely/not/here", ""])
def test_add_rejects_non_repos(client: TestClient, state: ConsoleState, bad: str) -> None:
    r = client.post("/api/repos", json={"path": bad}, headers=hdr(state))
    assert r.status_code == 400 and "error" in r.json()


def test_add_rejects_dir_without_git(client: TestClient, state: ConsoleState, tmp_path: Path) -> None:
    r = client.post("/api/repos", json={"path": str(tmp_path)}, headers=hdr(state))
    assert r.status_code == 400 and "not a git repository" in r.json()["error"]


def test_health_matches_cli(client: TestClient, state: ConsoleState, project: Path) -> None:
    (project / "docs/API.md").write_text("# API\n\n[bad](nope.md)\n", encoding="utf-8")
    client.post("/api/repos", json={"path": str(project)}, headers=hdr(state))
    cli = CliRunner().invoke(cli_app, ["check", "--path", str(project), "--format", "json"])
    summary = json.loads(cli.output)["summary"]
    h = health.compute(project)
    assert (h.errors, h.warnings) == (summary["error"], summary["warn"])
    page = client.get("/").text
    assert "Failing" in page


def test_uninitialised_repo_shows_setup(client: TestClient, state: ConsoleState, repo: Path) -> None:
    commit_all(repo, "empty")
    client.post("/api/repos", json={"path": str(repo)}, headers=hdr(state))
    assert "Not set up" in client.get("/").text


def test_no_external_resources(client: TestClient) -> None:
    page = client.get("/").text
    assert "http://" not in page.replace(BASE, "") and "https://" not in page


# --- T14: repo detail, manual, usage (DoD 8.4, 8.5) --------------------------------------------------------------


def add_project(client: TestClient, state: ConsoleState, path: Path) -> str:
    return str(client.post("/api/repos", json={"path": str(path)}, headers=hdr(state)).json()["id"])


def test_repo_detail_coverage_and_adrs(client: TestClient, state: ConsoleState, project: Path) -> None:
    (project / "docs/adr/001-use-pandoc.md").write_text(
        "# ADR-001: Use pandoc\n\n## Status\n\nAccepted\n", encoding="utf-8")
    (project / "docs/API.md").unlink()
    rid = add_project(client, state, project)
    page = client.get(f"/repos/{rid}").text
    assert "Use pandoc" in page and "Accepted" in page
    assert "docs/API.md" in page and "missing" in page
    assert "12/13" in page  # 13 typed docs (README + 12), API.md missing


def test_repo_detail_unknown_is_404(client: TestClient) -> None:
    assert client.get("/repos/nope").status_code == 404


HAVE_TEX = __import__("shutil").which("pandoc") and __import__("shutil").which("tectonic")


@pytest.mark.skipif(not HAVE_TEX, reason="pandoc/tectonic not installed")
def test_manual_build_and_inline_preview(client: TestClient, state: ConsoleState, project: Path) -> None:
    rid = add_project(client, state, project)
    assert "No manual built yet" in client.get(f"/repos/{rid}/manual").text
    r = client.post(f"/api/repos/{rid}/build", headers=hdr(state))
    assert r.status_code == 200, r.text
    assert "manual" in client.get(f"/repos/{rid}/manual").text
    pdf = client.get(f"/repos/{rid}/manual.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-disposition"].startswith("inline")


def test_manual_build_needs_token(client: TestClient, project: Path, state: ConsoleState) -> None:
    rid = add_project(client, state, project)
    assert client.post(f"/api/repos/{rid}/build").status_code == 403


def test_usage_matches_cli(client: TestClient) -> None:
    from types import SimpleNamespace

    from docforge.agent.budget import BudgetGuard

    g = BudgetGuard("impact", 0.5, 10.0)
    g.record(SimpleNamespace(input_tokens=1000, output_tokens=500, cache_read_input_tokens=0,
                             cache_creation_input_tokens=0))
    cli = CliRunner().invoke(cli_app, ["usage"]).output
    page = client.get("/usage").text
    assert g.run_id in page and "$0.0070" in page and "$0.0070" in cli
    assert "$0.01" in page  # month total rounded to cents
