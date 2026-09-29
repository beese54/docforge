"""The agent loop. Manual (not the SDK tool runner) so every call passes through the budget guard first."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic

from docforge.agent import prompts
from docforge.agent.budget import MODEL, BudgetExceeded, BudgetGuard
from docforge.agent.patch import make_patch
from docforge.agent.policy import TOOL_DEFS, ToolError, ToolLayer

MAX_TURNS = 40
EFFORT = "medium"


class AgentError(Exception):
    """The run failed; no patch is written. Maps to CLI exit code 3."""


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


def run(
    client: Any,  # anthropic.Anthropic, or a test fake exposing messages.create / messages.count_tokens
    tools: ToolLayer,
    guard: BudgetGuard,
    task: str,
    out_dir: Path,
) -> RunResult:
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    turns = 0
    try:
        while tools.report is None:
            turns += 1
            if turns > MAX_TURNS:
                raise AgentError(f"stopped after {MAX_TURNS} turns without calling finish")
            request: dict[str, Any] = {"model": MODEL, "system": _system(), "tools": TOOL_DEFS, "messages": messages}
            counted = client.messages.count_tokens(**request)
            max_tokens = guard.max_tokens_for(counted.input_tokens)
            response = client.messages.create(
                **request,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                output_config={"effort": EFFORT},
                cache_control={"type": "ephemeral"},
            )
            guard.record(response.usage)

            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                raise AgentError(f"model refused (category: {getattr(details, 'category', None)})")
            if response.stop_reason == "max_tokens":
                raise AgentError(f"response hit max_tokens={max_tokens} (budget-limited); nothing was applied")

            messages.append({"role": "assistant", "content": response.content})
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            if not tool_uses:
                # Ended without `finish`: keep its text as the report rather than lose it.
                tools.report = "\n\n".join(b.text for b in response.content if b.type == "text") or "(no report)"
                break
            results = []
            for block in tool_uses:
                try:
                    output, is_error = tools.dispatch(block.name, dict(block.input)), False
                except ToolError as exc:
                    output, is_error = str(exc), True
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
        raise AgentError("no Anthropic credentials (set ANTHROPIC_API_KEY or attach the OpenShell provider)") from exc

    return _write_outputs(tools, guard, out_dir, turns)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def _write_outputs(tools: ToolLayer, guard: BudgetGuard, out_dir: Path, turns: int) -> RunResult:
    patch = make_patch(tools.root, tools.staged)
    changed = sorted(tools.staged)
    policy_lines = [e.line() for e in tools.events]
    report = (
        f"{tools.report}\n\n---\n"
        f"Run `{guard.run_id}` ({guard.command}): {turns} model turn(s), cost ${guard.run_spent:.4f}. "
        f"Files in patch: {', '.join(changed) or 'none'}. Policy denials: {len(policy_lines)}.\n"
    )
    result = RunResult(out_dir / "docforge.patch", out_dir / "report.md", out_dir / "policy.log", changed,
                       guard.run_spent, turns)
    _atomic_write(result.patch_path, patch)
    _atomic_write(result.report_path, report)
    _atomic_write(result.policy_log, "\n".join(policy_lines) + ("\n" if policy_lines else ""))
    _atomic_write(out_dir / "run.json", json.dumps({"run_id": guard.run_id, "command": guard.command,
                                                    "cost_usd": round(guard.run_spent, 6), "turns": turns,
                                                    "files": changed}, indent=2))
    return result
