"""Access to the static files shipped in `docforge/templates/`."""

from __future__ import annotations

from importlib import resources


def read(name: str) -> str:
    return (resources.files("docforge") / "templates" / name).read_text(encoding="utf-8")
