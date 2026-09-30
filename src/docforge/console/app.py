"""FastAPI application for docforge Console.

Security model (local demo tool, but it can push with the user's GitHub login):
- `docforge serve` binds 127.0.0.1 only.
- Host check: requests whose Host header is not this server's localhost address are refused. This stops DNS
  rebinding, where a malicious website points its own hostname at 127.0.0.1.
- Launch token: `serve` prints a URL with a random token. Opening it sets an HttpOnly, SameSite=Strict cookie;
  every page needs that cookie, and every state-changing request must also send the token in a header, which
  only pages served by this app can read (from a meta tag).
"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from docforge import __version__, build
from docforge.config import DEFAULT_MONTHLY_USD, DEFAULT_PER_RUN_USD, ConfigError, load
from docforge.console import health, registry, views
from docforge.console import runs as runs_mod

HERE = Path(__file__).parent
COOKIE = "docforge_session"
TOKEN_HEADER = "x-docforge-token"


@dataclass
class ConsoleState:
    port: int
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    extra_hosts: tuple[str, ...] = ()

    @property
    def allowed_hosts(self) -> set[str]:
        return {f"127.0.0.1:{self.port}", f"localhost:{self.port}", *self.extra_hosts}

    def launch_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/auth?t={self.token}"


class HostCheck(BaseHTTPMiddleware):
    def __init__(self, app: Any, state: ConsoleState) -> None:
        super().__init__(app)
        self.state = state

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.headers.get("host", "") not in self.state.allowed_hosts:
            return JSONResponse({"error": "Host not allowed. Open the console at 127.0.0.1."}, status_code=403)
        return await call_next(request)


def create_app(state: ConsoleState, run_manager: runs_mod.RunManager | None = None) -> FastAPI:
    run_manager = run_manager or runs_mod.RunManager()
    app = FastAPI(title="docforge Console", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(HostCheck, state=state)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    templates = Jinja2Templates(directory=HERE / "templates")

    def session(request: Request) -> None:
        if not secrets.compare_digest(request.cookies.get(COOKIE, ""), state.token):
            raise HTTPException(401, "Open the link printed by `docforge serve` to start a session.")

    def action(request: Request) -> None:
        session(request)
        if not secrets.compare_digest(request.headers.get(TOKEN_HEADER, ""), state.token):
            raise HTTPException(403, "Missing or wrong action token.")

    def page(request: Request, name: str, **ctx: Any) -> HTMLResponse:
        return templates.TemplateResponse(
            request, name, {"token": state.token, "version": __version__, "active": name.split(".")[0], **ctx}
        )

    app.state.console = state
    app.state.page = page
    app.state.session = session
    app.state.action = action

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
        ctx = {"status": exc.status_code, "detail": exc.detail, "token": "", "version": __version__, "active": ""}
        return templates.TemplateResponse(request, "error.html", ctx, status_code=exc.status_code)

    @app.get("/auth")
    def auth(t: str = "") -> Response:
        if not secrets.compare_digest(t, state.token):
            raise HTTPException(401, "That link is not valid for this console session.")
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(COOKIE, state.token, httponly=True, samesite="strict")
        return resp

    @app.get("/", response_class=HTMLResponse, dependencies=[Depends(session)])
    def repos_page(request: Request) -> HTMLResponse:
        rows = [(r, health.compute(Path(r.path))) for r in registry.load()]
        return page(request, "repos.html", rows=rows)

    @app.post("/api/repos", dependencies=[Depends(action)])
    async def add_repo(request: Request) -> JSONResponse:
        body = await request.json()
        try:
            repo = registry.add(str(body.get("path", "")))
        except registry.RegistryError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse({"id": repo.id, "name": repo.name})

    @app.post("/api/repos/{rid}/remove", dependencies=[Depends(action)])
    def remove_repo(rid: str) -> JSONResponse:
        registry.remove(rid)
        return JSONResponse({"removed": rid})

    def repo_or_404(rid: str) -> registry.Repo:
        repo = registry.get(rid)
        if repo is None:
            raise HTTPException(404, "That repository is not in the console. Add it on the Repos screen.")
        return repo

    app.state.repo_or_404 = repo_or_404
    build_errors: dict[str, str] = {}

    @app.get("/repos/{rid}", response_class=HTMLResponse, dependencies=[Depends(session)])
    def repo_page(request: Request, rid: str) -> HTMLResponse:
        repo = repo_or_404(rid)
        root = Path(repo.path)
        return page(request, "repo.html", repo=repo, h=health.compute(root), docs=views.coverage(root),
                    adrs=views.adrs(root))

    def latest_pdf(root: Path) -> Path | None:
        pdfs = sorted((root / "documentation/build").glob("*.pdf"), key=lambda p: p.stat().st_mtime)
        return pdfs[-1] if pdfs else None

    @app.get("/repos/{rid}/manual", response_class=HTMLResponse, dependencies=[Depends(session)])
    def manual_page(request: Request, rid: str) -> HTMLResponse:
        repo = repo_or_404(rid)
        pdf = latest_pdf(Path(repo.path))
        built = datetime.fromtimestamp(pdf.stat().st_mtime).strftime("built %Y-%m-%d %H:%M") if pdf else ""
        return page(request, "manual.html", repo=repo, pdf=pdf.name if pdf else None, built=built,
                    error=build_errors.pop(rid, None))

    @app.get("/repos/{rid}/manual.pdf", dependencies=[Depends(session)])
    def manual_pdf(rid: str) -> FileResponse:
        pdf = latest_pdf(Path(repo_or_404(rid).path))
        if pdf is None:
            raise HTTPException(404, "No manual has been built yet.")
        return FileResponse(pdf, media_type="application/pdf", filename=pdf.name, content_disposition_type="inline")

    @app.post("/api/repos/{rid}/build", dependencies=[Depends(action)])
    def build_manual(rid: str) -> JSONResponse:
        root = Path(repo_or_404(rid).path)
        try:
            result = build.build(load(root))
        except (ConfigError, build.BuildError) as exc:
            build_errors[rid] = str(exc)
            return JSONResponse({"error": "Build failed; details are on the page."}, status_code=400)
        return JSONResponse({"message": f"Built {result.output.name} ({len(result.chapters)} chapters)"})

    @app.get("/usage", response_class=HTMLResponse, dependencies=[Depends(session)])
    def usage_page(request: Request) -> HTMLResponse:
        return page(request, "usage.html", s=views.spend())

    # -- agent runs ----------------------------------------------------------------------------------------------

    def job_or_404(job_id: str) -> runs_mod.Job:
        job = run_manager.get(job_id)
        if job is None:
            raise HTTPException(404, "That run is not in this console session.")
        return job

    app.state.runs = run_manager
    app.state.job_or_404 = job_or_404

    @app.get("/runs", response_class=HTMLResponse, dependencies=[Depends(session)])
    def runs_page(request: Request) -> HTMLResponse:
        return page(request, "runs.html", replays=runs_mod.replays(), jobs=run_manager.recent())

    @app.post("/api/replays/{name}", dependencies=[Depends(action)])
    def start_replay(name: str) -> JSONResponse:
        try:
            job = run_manager.start_replay(name)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        return JSONResponse({"go": f"/runs/{job.id}"})

    @app.get("/repos/{rid}/run", response_class=HTMLResponse, dependencies=[Depends(session)])
    def run_start_page(request: Request, rid: str) -> HTMLResponse:
        repo = repo_or_404(rid)
        root = Path(repo.path)
        try:
            cfg = load(root)
            caps, monthly, reason = cfg.budget.per_run_usd, cfg.budget.monthly_usd, ""
        except ConfigError as exc:
            caps, monthly, reason = dict(DEFAULT_PER_RUN_USD), DEFAULT_MONTHLY_USD, f"docforge.toml: {exc}"
        if run_manager.sandbox_dir is None:
            reason = "sandbox/run-agent.sh was not found (run the console from the docforge checkout)"
        return page(request, "run_start.html", repo=repo, replays=runs_mod.replays(), caps=caps, monthly=monthly,
                    live_ok=not reason, live_reason=reason)

    @app.post("/api/repos/{rid}/runs", dependencies=[Depends(action)])
    async def start_run(request: Request, rid: str) -> JSONResponse:
        repo = repo_or_404(rid)
        body = await request.json()
        if body.get("mode", "replay") == "replay":
            return start_replay(str(body.get("replay", "")))
        task = str(body.get("task", ""))
        extra: list[str] = []
        if task == "impact" and str(body.get("base", "")).strip():
            extra += ["--base", str(body["base"]).strip()]
        if task == "adr":
            title = str(body.get("title", "")).strip()
            if not title:
                return JSONResponse({"error": "An ADR needs a decision title."}, status_code=400)
            extra = [title] + (["--note", str(body["note"]).strip()] if str(body.get("note", "")).strip() else [])
        try:
            job = run_manager.start_live(rid, Path(repo.path), task, extra, f"{task} on {repo.name}")
        except runs_mod.BusyError as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)
        except (ValueError, FileNotFoundError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse({"go": f"/runs/{job.id}"})

    @app.get("/runs/{job_id}", response_class=HTMLResponse, dependencies=[Depends(session)])
    def run_page(request: Request, job_id: str) -> HTMLResponse:
        return page(request, "run.html", job=job_or_404(job_id))

    @app.get("/api/runs/{job_id}/stream", dependencies=[Depends(session)])
    async def run_stream(job_id: str) -> StreamingResponse:
        job = job_or_404(job_id)

        async def events() -> AsyncIterator[str]:
            sent = 0
            while True:
                while sent < len(job.lines):
                    yield f"event: line\ndata: {json.dumps(job.lines[sent])}\n\n"
                    sent += 1
                if job.status != "running" and sent >= len(job.lines):
                    yield f"event: done\ndata: {json.dumps(job.summary())}\n\n"
                    return
                await asyncio.sleep(0.15)

        return StreamingResponse(events(), media_type="text/event-stream", headers={"cache-control": "no-store"})

    @app.get("/runs/{job_id}/review", response_class=HTMLResponse, dependencies=[Depends(session)])
    def review_page(request: Request, job_id: str) -> HTMLResponse:
        job = job_or_404(job_id)
        files = runs_mod.review_files(job.out_dir)
        patch = files["patch"] or ""
        policy = files["policy"] or ""
        return page(request, "review.html", job=job, patch=bool(files["patch"]), partial=bool(files["partial"]),
                    diff=views.diff_lines(patch or files["partial"] or ""),
                    files=views.patch_files(patch or files["partial"] or ""),
                    report_html=views.render_report(files["report"] or "_No report was written._"),
                    policy=policy, denials=len([ln for ln in policy.splitlines() if ln.strip()]),
                    extra=review_extra(job))

    def review_extra(job: runs_mod.Job) -> dict[str, Any]:
        """Hook for the apply/push/PR panel (T16)."""
        hook = getattr(app.state, "review_extra", None)
        return dict(hook(job)) if hook else {}

    return app
