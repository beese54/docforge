"""Agent runs for the console: replays of recorded runs, and live runs through sandbox/run-agent.sh.

A replay streams a real recorded trace at a readable pace and then shows the recorded report and patch. It never
calls the model, never spends, and can never be applied or pushed. A live run starts the same script a developer
would, inside OpenShell, with the normal budget caps; only one live run is allowed at a time.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

REPLAY_ROOT = Path(str(resources.files("docforge.console") / "replays"))
AGENT_OUT = "documentation/build/agent"
TASKS = ("impact", "adr", "bootstrap")
_COST = re.compile(r"^turn\s+\d+\s+\$(\d+\.\d+)")


def default_sandbox_dir() -> Path | None:
    """The sandbox/ scripts live in the docforge checkout, next to src/."""
    candidate = Path(__file__).resolve().parents[3] / "sandbox" / "run-agent.sh"
    return candidate.parent if candidate.is_file() else None


@dataclass(frozen=True)
class Replay:
    name: str
    title: str
    repo: str
    task: str
    detail: str
    cost_usd: float
    turns: int
    files: list[str]

    @property
    def dir(self) -> Path:
        return REPLAY_ROOT / self.name


def replays() -> list[Replay]:
    out: list[Replay] = []
    for d in sorted(p for p in REPLAY_ROOT.iterdir() if p.is_dir()):
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        run = json.loads((d / "run.json").read_text(encoding="utf-8"))
        out.append(Replay(d.name, meta["title"], meta["repo"], meta["task"], meta["detail"], run["cost_usd"],
                          run["turns"], run["files"]))
    return out


def classify(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("turn"):
        return "turn"
    if "ERROR" in line or stripped.startswith("FAILED") or line.startswith("error:"):
        return "error"
    if stripped.startswith(("report:", "patch:", "cost:", "sandbox exit", "Created sandbox", "Uploading", "Downloading",
                            "✓", "[")):
        return "meta"
    return "tool"


@dataclass
class Job:
    id: str
    mode: str  # "replay" | "live"
    task: str
    title: str
    repo_id: str | None
    out_dir: Path
    lines: list[dict[str, str]] = field(default_factory=list)
    status: str = "running"  # running | ok | failed
    started: float = field(default_factory=time.time)
    finished: float | None = None
    cost: float = 0.0
    exit_code: int | None = None

    def add(self, text: str) -> None:
        m = _COST.match(text.strip())
        if m:
            self.cost += float(m.group(1))
        self.lines.append({"text": text.rstrip(), "kind": classify(text)})

    def summary(self) -> dict[str, Any]:
        return {"status": self.status, "mode": self.mode, "cost": round(self.cost, 4), "lines": len(self.lines),
                "review": f"/runs/{self.id}/review", "exit_code": self.exit_code}


class BusyError(Exception):
    """A live run is already in progress."""


class RunManager:
    def __init__(self, sandbox_dir: Path | None = None, replay_delay: float = 0.12,
                 command: Callable[[Path, str, list[str]], list[str]] | None = None) -> None:
        self.jobs: dict[str, Job] = {}
        self.sandbox_dir = sandbox_dir if sandbox_dir is not None else default_sandbox_dir()
        self.replay_delay = replay_delay
        self._command = command or self._run_agent_command
        self._lock = threading.Lock()

    def _run_agent_command(self, repo: Path, task: str, extra: list[str]) -> list[str]:
        if self.sandbox_dir is None:
            raise FileNotFoundError("sandbox/run-agent.sh not found; live runs need the docforge checkout")
        return ["bash", str(self.sandbox_dir / "run-agent.sh"), str(repo), task, *extra]

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def recent(self) -> list[Job]:
        return sorted(self.jobs.values(), key=lambda j: j.started, reverse=True)

    # -- replay --------------------------------------------------------------------------------------------------

    def start_replay(self, name: str) -> Job:
        replay = next((r for r in replays() if r.name == name), None)
        if replay is None:
            raise KeyError(f"no replay named {name!r}")
        job = Job(uuid.uuid4().hex[:10], "replay", replay.task, replay.title, None, replay.dir)
        self.jobs[job.id] = job
        threading.Thread(target=self._play, args=(job, replay), daemon=True).start()
        return job

    def _play(self, job: Job, replay: Replay) -> None:
        job.add(f"Replay of a recorded run ({replay.repo}, {replay.task}). No model is called and nothing is spent.")
        job.add("Created sandbox (recorded) · repo copy uploaded · agent started")
        for line in (replay.dir / "trace.log").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            time.sleep(self.replay_delay * (3 if line.lstrip().startswith("turn") else 1))
            job.add(line)
        job.add(f"patch: {len(replay.files)} file(s) · recorded cost ${replay.cost_usd:.4f} over {replay.turns} turns")
        job.cost = replay.cost_usd
        job.status, job.exit_code, job.finished = "ok", 0, time.time()

    # -- live ------------------------------------------------------------------------------------------------

    def start_live(self, repo_id: str, repo: Path, task: str, extra: list[str], title: str) -> Job:
        if task not in TASKS:
            raise ValueError(f"unknown task {task!r}")
        with self._lock:
            if any(j.mode == "live" and j.status == "running" for j in self.jobs.values()):
                raise BusyError("A live run is already in progress. Wait for it to finish.")
            cmd = self._command(repo, task, extra)
            job = Job(uuid.uuid4().hex[:10], "live", task, title, repo_id, repo / AGENT_OUT)
            self.jobs[job.id] = job
        threading.Thread(target=self._execute, args=(job, cmd), daemon=True).start()
        return job

    def _execute(self, job: Job, cmd: list[str]) -> None:
        job.add("$ " + " ".join(cmd[1:] if cmd[0] == "bash" else cmd))
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    text=True, bufsize=1)
        except OSError as exc:
            job.add(f"error: could not start the run: {exc}")
            job.status, job.exit_code, job.finished = "failed", 127, time.time()
            return
        assert proc.stdout is not None
        for line in proc.stdout:
            if line.strip():
                job.add(line)
        job.exit_code = proc.wait()
        job.status = "ok" if job.exit_code == 0 else "failed"
        job.finished = time.time()


def review_files(out_dir: Path) -> dict[str, str | None]:
    """The artefacts a run left behind; a failed run may have only a partial patch."""
    def read(name: str) -> str | None:
        p = out_dir / name
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else None

    return {
        "patch": read("docforge.patch"),
        "partial": read("docforge.partial.patch"),
        "report": read("report.md"),
        "policy": read("policy.log"),
        "trace": read("trace.log"),
    }
