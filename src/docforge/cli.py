"""Command-line entry point. Each command lives in its own module; this file only wires them up."""

from __future__ import annotations

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
