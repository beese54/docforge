"""The list of repositories the console shows, kept in $DOCFORGE_HOME/console.json."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from docforge.agent.budget import ledger_path


class RegistryError(Exception):
    """A repository cannot be added (missing, not a directory, not a git repo)."""


@dataclass(frozen=True)
class Repo:
    id: str
    path: str
    name: str


def repo_id(path: Path) -> str:
    return hashlib.sha256(str(path).encode()).hexdigest()[:10]


def registry_path() -> Path:
    return ledger_path().parent / "console.json"


def load() -> list[Repo]:
    path = registry_path()
    if not path.is_file():
        return []
    try:
        return [Repo(**r) for r in json.loads(path.read_text(encoding="utf-8"))]
    except (json.JSONDecodeError, TypeError):
        return []


def _save(repos: list[Repo]) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in repos], indent=2), encoding="utf-8")


def add(raw_path: str) -> Repo:
    raw_path = raw_path.strip()
    # An empty or relative path would silently resolve against the server's working directory.
    if not raw_path or not Path(raw_path).expanduser().is_absolute():
        raise RegistryError("Give the full path to the repository, for example /home/you/project")
    path = Path(raw_path).expanduser().resolve()
    if not path.is_dir():
        raise RegistryError(f"{path} is not a directory")
    if not (path / ".git").exists():
        raise RegistryError(f"{path} is not a git repository")
    repos = load()
    rid = repo_id(path)
    existing = next((r for r in repos if r.id == rid), None)
    if existing:
        return existing
    repo = Repo(id=rid, path=str(path), name=path.name)
    _save([*repos, repo])
    return repo


def remove(rid: str) -> None:
    _save([r for r in load() if r.id != rid])


def get(rid: str) -> Repo | None:
    return next((r for r in load() if r.id == rid), None)
