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


class BuildFormat(StrEnum):
    pdf = "pdf"
    tex = "tex"


@app.command()
def build(
    path: RepoPath = Path("."),
    out: Annotated[Path | None, typer.Option("--out", help="Output directory (default documentation/build).")] = None,
    fmt: Annotated[BuildFormat, typer.Option("--format", help="pdf, or tex to inspect the LaTeX.")] = BuildFormat.pdf,
    strict: Annotated[bool, typer.Option("--strict", help="Fail if a Mermaid diagram cannot be rendered.")] = False,
) -> None:
    """Build the versioned technical manual: Markdown -> pandoc -> LaTeX -> PDF."""
    from docforge.build import BuildError
    from docforge.build import build as run_build
    from docforge.config import ConfigError, load

    try:
        result = run_build(load(path), out_dir=out, fmt=fmt.value, strict=strict)
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    except BuildError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(exc.code) from exc
    for warning in result.warnings:
        typer.echo(f"warning: {warning}", err=True)
    typer.echo(f"{result.output} ({len(result.chapters)} chapters, version {result.version.describe})")


# --- agent ------------------------------------------------------------------------------------------------

agent_app = typer.Typer(no_args_is_help=True, help="AI documentation agent. Proposes a patch; never applies it.")
app.add_typer(agent_app, name="agent")

OutDir = Annotated[
    Path | None, typer.Option("--out", help="Where to write docforge.patch and report.md.", resolve_path=True)
]
DEFAULT_AGENT_OUT = "documentation/build/agent"


def _run_agent(path: Path, command: str, out: Path | None, base: str | None, task: str) -> None:
    import anthropic

    from docforge import git
    from docforge.agent.budget import BudgetGuard
    from docforge.agent.policy import ToolLayer
    from docforge.agent.runner import AgentError, run
    from docforge.config import ConfigError, load

    try:
        cfg = load(path)
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not git.is_repo(path):
        typer.echo("error: not a git repository", err=True)
        raise typer.Exit(2)
    if base is not None:
        try:
            git.resolve(path, base)
        except git.GitError as exc:
            typer.echo(f"error: base ref '{base}' not found", err=True)
            raise typer.Exit(2) from exc
    try:
        client = anthropic.Anthropic()
    except anthropic.AnthropicError as exc:
        typer.echo(f"error: no Anthropic credentials ({exc})", err=True)
        raise typer.Exit(3) from exc

    guard = BudgetGuard(command, cfg.budget.per_run_usd.get(command, 0.50), cfg.budget.monthly_usd)
    try:
        result = run(client, ToolLayer(root=path, base=base), guard, task, out or path / DEFAULT_AGENT_OUT)
    except AgentError as exc:
        typer.echo(f"error: {exc} (spent ${guard.run_spent:.4f}; no patch written)", err=True)
        raise typer.Exit(3) from exc
    typer.echo(f"report: {result.report_path}")
    typer.echo(f"patch:  {result.patch_path} ({len(result.files_changed)} file(s): {', '.join(result.files_changed)})")
    typer.echo(f"cost:   ${result.cost_usd:.4f} over {result.turns} turn(s)")
    typer.echo(f"Review the report and patch, then: docforge apply {result.patch_path}")


@agent_app.command("impact")
def agent_impact(
    path: RepoPath = Path("."),
    base: Annotated[str | None, typer.Option("--base", help="Compare against (default: merge-base with main).")] = None,
    out: OutDir = None,
) -> None:
    """Documentation impact check for base..working tree; proposes doc updates, ADRs and a CHANGELOG entry."""
    from docforge import git
    from docforge.agent import prompts

    ref = base or (git.default_base(path) if git.is_repo(path) else None)
    if ref is None:
        typer.echo("error: no base ref to compare with; pass --base", err=True)
        raise typer.Exit(2)
    _run_agent(path, "impact", out, ref, prompts.impact_task(ref))


@agent_app.command("adr")
def agent_adr(
    title: Annotated[str, typer.Argument(help="Decision title.")],
    note: Annotated[str, typer.Option("--note", help="Context from the developer.")] = "",
    path: RepoPath = Path("."),
    out: OutDir = None,
) -> None:
    """Draft the next-numbered ADR (Status: Proposed)."""
    from docforge.agent import prompts

    _run_agent(path, "adr", out, None, prompts.adr_task(title, note))


@agent_app.command("bootstrap")
def agent_bootstrap(path: RepoPath = Path("."), out: OutDir = None) -> None:
    """First documentation pass over an existing repository."""
    from docforge.agent import prompts

    _run_agent(path, "bootstrap", out, None, prompts.bootstrap_task())


@app.command()
def usage(
    last: Annotated[bool, typer.Option("--last", help="Only the most recent run.")] = False,
) -> None:
    """Show model spend from the local usage ledger (~/.docforge/usage.jsonl)."""
    from collections import defaultdict

    from docforge.agent.budget import month_spend, read_ledger

    records = read_ledger()
    if not records:
        typer.echo("No usage recorded.")
        return
    runs: dict[str, list[float]] = defaultdict(list)
    meta: dict[str, tuple[str, str]] = {}
    for r in records:
        runs[r.run_id].append(r.cost_usd)
        meta.setdefault(r.run_id, (r.ts, r.command))
    ids = list(runs)[-1:] if last else list(runs)
    for run_id in ids:
        ts, command = meta[run_id]
        typer.echo(f"{ts}  {command:9} run {run_id}  ${sum(runs[run_id]):.4f}  ({len(runs[run_id])} call(s))")
    total = sum(r.cost_usd for r in records)
    typer.echo(f"this month ${month_spend(records):.4f}  total ${total:.4f}")
