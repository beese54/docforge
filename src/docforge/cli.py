"""Command-line entry point. Each command lives in its own module; this file only wires them up."""

from __future__ import annotations

from pathlib import Path

import typer

from docforge import __version__

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Docs-as-code for AI-assisted projects.")


def _version(value: bool) -> None:
    if value:
        typer.echo(f"docforge {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", callback=_version, is_eager=True, help="Show version."),
) -> None:
    """docforge: scaffold, check, build and agent-maintain project documentation."""


PathOpt = typer.Option(Path("."), "--path", help="Repository root.", file_okay=False, resolve_path=True)


@app.command()
def init(path: Path = PathOpt) -> None:
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
