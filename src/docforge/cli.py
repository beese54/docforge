"""Command-line entry point. Each command lives in its own module; this file only wires them up."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from docforge import __version__

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Docs-as-code for AI-assisted projects.")

RepoPath = Annotated[
    Path, typer.Option("--path", help="Repository root.", file_okay=False, resolve_path=True)
]


class OutputFormat(StrEnum):
    text = "text"
    json = "json"


def _version(value: bool) -> None:
    if value:
        typer.echo(f"docforge {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")
    ] = False,
) -> None:
    """docforge: scaffold, check, build and agent-maintain project documentation."""


@app.command()
def init(path: RepoPath = Path(".")) -> None:
    """Create the documentation structure. Only missing files are created; nothing is overwritten."""
    from docforge.init import scaffold

    created, skipped = scaffold(path)
    for rel in created:
        typer.echo(f"  created  {rel}")
    for rel in skipped:
        typer.echo(f"  exists   {rel}")
    if created:
        typer.echo(f"{len(created)} file(s) created. Review docforge.toml's impact map, then fill the docs.")
    else:
        typer.echo("Nothing to do: every file already exists.")


@app.command()
def check(
    path: RepoPath = Path("."),
    strict: Annotated[
        bool, typer.Option("--strict", help="CI mode: soft rules and ADR-worthy drift become errors.")
    ] = False,
    output: Annotated[OutputFormat, typer.Option("--format", help="Output format.")] = OutputFormat.text,
    base: Annotated[
        str | None, typer.Option("--base", help="Git ref to compare against for drift (default: merge-base with main).")
    ] = None,
) -> None:
    """Check docs: structure, sections, links, ADRs, uncertain markers and code/doc drift. Exit 1 on errors."""
    from docforge import checks, drift
    from docforge.config import ConfigError, load
    from docforge.findings import Severity

    try:
        cfg = load(path)
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc

    findings = checks.run(cfg, strict=strict, extra=(drift.make_check(base),))
    summary = {str(s): sum(1 for f in findings if f.severity == s) for s in Severity}
    if output is OutputFormat.json:
        typer.echo(json.dumps({"findings": [f.to_dict() for f in findings], "summary": summary}, indent=2))
    else:
        for f in findings:
            typer.echo(f.to_text())
        typer.echo(f"{summary['error']} error(s), {summary['warn']} warning(s), {summary['info']} info")
    raise typer.Exit(1 if summary["error"] else 0)
