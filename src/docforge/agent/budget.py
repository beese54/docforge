"""Hard spend caps, enforced by construction, plus the usage ledger.

Before every call the guard sizes `max_tokens` so that the worst case (every input token billed at the
cache-write rate, every output token used) still fits the remaining per-run and monthly allowance. The cap
therefore cannot be exceeded by a single call; if too little remains for a useful answer, the call is refused.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

MODEL = "claude-sonnet-5-5"
# USD per token. Source: claude-api skill model table (cached 2026-09-25): $2 in / $10 out per MTok,
# cache reads $0.20/MTok; 5-minute cache writes bill at 1.25x input.
PRICES: dict[str, dict[str, float]] = {
    "claude-sonnet-5-5": {"input": 2.00e-6, "output": 10.00e-6, "cache_read": 0.20e-6, "cache_write": 2.50e-6},
}
MAX_OUTPUT_TOKENS = 32_000  # per response (streamed); the guard still shrinks it to fit the remaining budget
MIN_USEFUL_OUTPUT = 2_048


class BudgetExceeded(Exception):
    """Refused before calling the model: the remaining allowance cannot cover a useful response."""


def ledger_path() -> Path:
    home = Path(os.environ.get("DOCFORGE_HOME", Path.home() / ".docforge"))
    return home / "usage.jsonl"


@dataclass(frozen=True)
class UsageRecord:
    ts: str
    run_id: str
    command: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: float
    note: str = ""


def cost_of(model: str, usage: Any) -> float:
    price = PRICES[model]
    return (
        getattr(usage, "input_tokens", 0) * price["input"]
        + getattr(usage, "output_tokens", 0) * price["output"]
        + (getattr(usage, "cache_read_input_tokens", 0) or 0) * price["cache_read"]
        + (getattr(usage, "cache_creation_input_tokens", 0) or 0) * price["cache_write"]
    )


def read_ledger(path: Path | None = None) -> list[UsageRecord]:
    path = path or ledger_path()
    if not path.is_file():
        return []
    return [UsageRecord(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def month_spend(records: list[UsageRecord], today: dt.date | None = None) -> float:
    prefix = (today or dt.date.today()).strftime("%Y-%m")
    return sum(r.cost_usd for r in records if r.ts.startswith(prefix))


class BudgetGuard:
    def __init__(self, command: str, per_run_usd: float, monthly_usd: float, ledger: Path | None = None) -> None:
        self.command = command
        self.per_run_usd = per_run_usd
        self.monthly_usd = monthly_usd
        self.ledger = ledger or ledger_path()
        self.run_id = uuid.uuid4().hex[:12]
        self.run_spent = 0.0
        self._month_before = month_spend(read_ledger(self.ledger))

    def allowance(self) -> float:
        return min(self.per_run_usd - self.run_spent, self.monthly_usd - self._month_before - self.run_spent)

    def max_tokens_for(self, input_tokens: int, model: str = MODEL) -> int:
        """Largest max_tokens whose worst-case cost fits the allowance. Raises BudgetExceeded if too small."""
        price = PRICES[model]
        left = self.allowance() - input_tokens * price["cache_write"]
        affordable = int(left / price["output"]) if left > 0 else 0
        max_tokens = min(MAX_OUTPUT_TOKENS, affordable)
        if max_tokens < MIN_USEFUL_OUTPUT:
            self._append(model, None, 0.0, note=f"refused: {input_tokens} input tokens, ${self.allowance():.4f} left")
            raise BudgetExceeded(
                f"budget exhausted for '{self.command}': ${self.run_spent:.4f} spent this run, "
                f"${self.allowance():.4f} left (per-run cap ${self.per_run_usd:.2f}, "
                f"monthly cap ${self.monthly_usd:.2f})"
            )
        return max_tokens

    def record(self, usage: Any, model: str = MODEL) -> float:
        cost = cost_of(model, usage)
        self.run_spent += cost
        self._append(model, usage, cost)
        return cost

    def _append(self, model: str, usage: Any, cost: float, note: str = "") -> None:
        rec = UsageRecord(
            ts=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            run_id=self.run_id,
            command=self.command,
            model=model,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            cache_read_tokens=(getattr(usage, "cache_read_input_tokens", 0) or 0) if usage else 0,
            cache_write_tokens=(getattr(usage, "cache_creation_input_tokens", 0) or 0) if usage else 0,
            cost_usd=round(cost, 6),
            note=note,
        )
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(rec)) + "\n")
