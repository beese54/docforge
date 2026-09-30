"""The agent loop. Manual (not the SDK tool runner) so every call passes through the budget guard first."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
import httpx2  # the SDK's HTTP client; a stream cut mid-body surfaces as httpx2.RemoteProtocolError

from docforge.agent import prompts
from docforge.agent.budget import MODEL, BudgetExceeded, BudgetGuard
from docforge.agent.patch import make_patch
from docforge.agent.policy import TOOL_DEFS, ToolError, ToolLayer

# A bootstrap reads ~20 files and writes ~20 docs; an impact check touches a handful.
MAX_TURNS: dict[str, int] = {"impact": 40, "adr": 20, "bootstrap": 120}
DEFAULT_MAX_TURNS = 40
EFFORT = "medium"
PARTIAL_PATCH = "docforge.partial.patch"
STREAM_ATTEMPTS = 3
RETRY_BASE_SECONDS = 2.0


class AgentError(Exception):
    """The run failed. No docforge.patch is written (maps to CLI exit code 3); see trace.log and, if any documents
    were finished, docforge.partial.patch."""


@dataclass
class RunResult:
    patch_path: Path
    report_path: Path
    policy_log: Path
    files_changed: list[str]
    cost_usd: float
    turns: int


def _system() -> list[dict[str, Any]]:
    return [{"type": "text", "text": prompts.SYSTEM}]


def _describe(name: str, args: dict[str, Any]) -> str:
    if name == "write_doc":
        return f"{args.get('path')} ({len(str(args.get('content', '')))} chars)"
    if name == "grep":
        return f"{args.get('pattern')!r} in {args.get('path_glob')}"
    for key in ("path", "directory"):
        if key in args:
            return str(args[key]) or "."
    return ""


def _log(trace: list[str], line: str) -> None:
    """Record a trace line; with DOCFORGE_PROGRESS set, also stream it to stderr (the console shows it live)."""
    trace.append(line)
    if os.environ.get("DOCFORGE_PROGRESS"):
        print(line, file=sys.stderr, flush=True)


def run(
    client: Any,  # anthropic.Anthropic, or a test fake exposing messages.stream / messages.count_tokens
    tools: ToolLayer,
    guard: BudgetGuard,
    task: str,
    out_dir: Path,
) -> RunResult:
    trace: list[str] = []
    turns = 0
    max_turns = MAX_TURNS.get(guard.command, DEFAULT_MAX_TURNS)
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    try:
        try:
            while tools.report is None:
                turns += 1
                if turns > max_turns:
                    raise AgentError(f"stopped after {max_turns} turns without calling finish")
                request: dict[str, Any] = {"model": MODEL, "system": _system(), "tools": TOOL_DEFS,
                                           "messages": messages}
                counted = client.messages.count_tokens(**request)
                for attempt in range(1, STREAM_ATTEMPTS + 1):
                    max_tokens = guard.max_tokens_for(counted.input_tokens)
                    try:
                        # Streaming: the SDK requires it for large max_tokens to avoid HTTP timeouts.
                        with client.messages.stream(
                            **request,
                            max_tokens=max_tokens,
                            thinking={"type": "adaptive"},
                            output_config={"effort": EFFORT},
                            cache_control={"type": "ephemeral"},
                        ) as stream:
                            response = stream.get_final_message()
                        break
                    except (anthropic.APIConnectionError, httpx2.TransportError) as exc:
                        # A dropped stream is safe to retry: no tool has run for this turn yet.
                        charged = guard.charge_worst_case(counted.input_tokens, max_tokens, type(exc).__name__)
                        _log(trace, f"turn {turns:3d}  stream interrupted ({type(exc).__name__}), attempt "
                                     f"{attempt}/{STREAM_ATTEMPTS}, worst case ${charged:.4f} charged")
                        if attempt == STREAM_ATTEMPTS:
                            raise AgentError(f"stream interrupted {STREAM_ATTEMPTS} times: {exc}") from exc
                        time.sleep(RETRY_BASE_SECONDS * 2 ** (attempt - 1))
                cost = guard.record(response.usage)
                _log(trace, f"turn {turns:3d}  ${cost:.4f}  stop={response.stop_reason}  "
                             f"out={getattr(response.usage, 'output_tokens', 0)}")

                if response.stop_reason == "refusal":
                    details = getattr(response, "stop_details", None)
                    raise AgentError(f"model refused (category: {getattr(details, 'category', None)})")
                if response.stop_reason == "max_tokens":
                    raise AgentError(f"a response hit max_tokens={max_tokens}; that response was discarded")

                messages.append({"role": "assistant", "content": response.content})
                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if not tool_uses:
                    # Ended without `finish`: keep its text as the report rather than lose it.
                    tools.report = "\n\n".join(b.text for b in response.content if b.type == "text") or "(no report)"
                    break
                results = []
                for block in tool_uses:
                    args = dict(block.input)
                    try:
                        output, is_error = tools.dispatch(block.name, args), False
                    except ToolError as exc:
                        output, is_error = str(exc), True
                    _log(trace, f"           {block.name:10} {_describe(block.name, args)}"
                                 + ("  -> ERROR " + output[:120] if is_error else ""))
                    results.append(
                        {"type": "tool_result", "tool_use_id": block.id, "content": output, "is_error": is_error}
                    )
                messages.append({"role": "user", "content": results})
        except BudgetExceeded as exc:
            raise AgentError(str(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise AgentError(f"could not reach the Anthropic API: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise AgentError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
        except TypeError as exc:
            # SDK 1.x resolves credentials lazily and raises TypeError on the first request when there are none.
            if "authentication" not in str(exc):
                raise
            raise AgentError(
                "no Anthropic credentials (set ANTHROPIC_API_KEY or attach the OpenShell provider)"
            ) from exc
    except Exception as exc:
        # Any failure, anticipated or not, keeps the trace and whatever documents were already paid for.
        _write_failure(tools, guard, out_dir, turns, trace, f"{type(exc).__name__}: {exc}")
        raise

    return _write_outputs(tools, guard, out_dir, turns, trace)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _write_common(tools: ToolLayer, guard: BudgetGuard, out_dir: Path, turns: int, trace: list[str],
                  status: str) -> None:
    policy_lines = [e.line() for e in tools.events]
    _atomic_write(out_dir / "policy.log", "\n".join(policy_lines) + ("\n" if policy_lines else ""))
    _atomic_write(out_dir / "trace.log", "\n".join(trace) + "\n")
    _atomic_write(out_dir / "run.json", json.dumps({
        "run_id": guard.run_id, "command": guard.command, "status": status,
        "cost_usd": round(guard.run_spent, 6), "turns": turns, "files": sorted(tools.staged),
    }, indent=2))


def _write_failure(tools: ToolLayer, guard: BudgetGuard, out_dir: Path, turns: int, trace: list[str],
                   reason: str) -> None:
    """Keep what was paid for: finished documents go to a separately named partial patch, never docforge.patch."""
    for stale in ("docforge.patch", "report.md"):
        (out_dir / stale).unlink(missing_ok=True)
    _write_common(tools, guard, out_dir, turns, trace + [f"FAILED: {reason}"], "failed")
    if tools.staged:
        _atomic_write(out_dir / PARTIAL_PATCH, make_patch(tools.root, tools.staged))


def _write_outputs(tools: ToolLayer, guard: BudgetGuard, out_dir: Path, turns: int, trace: list[str]) -> RunResult:
    patch = make_patch(tools.root, tools.staged)
    changed = sorted(tools.staged)
    report = (
        f"{tools.report}\n\n---\n"
        f"Run `{guard.run_id}` ({guard.command}): {turns} model turn(s), cost ${guard.run_spent:.4f}. "
        f"Files in patch: {', '.join(changed) or 'none'}. Policy denials: {len(tools.events)}.\n"
    )
    (out_dir / PARTIAL_PATCH).unlink(missing_ok=True)
    _write_common(tools, guard, out_dir, turns, trace, "ok")
    result = RunResult(out_dir / "docforge.patch", out_dir / "report.md", out_dir / "policy.log", changed,
                       guard.run_spent, turns)
    _atomic_write(result.patch_path, patch)
    _atomic_write(result.report_path, report)
    return result
