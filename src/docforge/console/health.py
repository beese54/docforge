"""Documentation health for one repository, computed with the same checks as `docforge check`."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docforge import checks, drift
from docforge.config import ConfigError, load
from docforge.findings import Finding, Severity

AGENT_OUT = "documentation/build/agent"


@dataclass
class Health:
    initialised: bool
    error: str | None = None
    findings: list[Finding] = field(default_factory=list)
    last_run: dict[str, Any] | None = None

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    @property
    def errors(self) -> int:
        return self.count(Severity.ERROR)

    @property
    def warnings(self) -> int:
        return self.count(Severity.WARN)

    @property
    def drift(self) -> int:
        return sum(1 for f in self.findings if f.rule == "drift" and f.severity >= Severity.WARN)

    @property
    def uncertain(self) -> int:
        total = 0
        for f in self.findings:
            if f.rule == "uncertain" and f.severity == Severity.INFO and "statement(s)" in f.message:
                total += int(f.message.split()[0])
        return total

    @property
    def state(self) -> str:
        """One word for the status pill."""
        if not self.initialised or self.error:
            return "setup"
        if self.errors:
            return "failing"
        if self.warnings:
            return "attention"
        return "healthy"


def last_agent_run(root: Path) -> dict[str, Any] | None:
    run = root / AGENT_OUT / "run.json"
    try:
        return json.loads(run.read_text(encoding="utf-8")) if run.is_file() else None
    except json.JSONDecodeError:
        return None


def compute(root: Path, strict: bool = False) -> Health:
    if not (root / "docforge.toml").is_file():
        return Health(initialised=False, last_run=last_agent_run(root))
    try:
        cfg = load(root)
    except ConfigError as exc:
        return Health(initialised=True, error=str(exc))
    findings = checks.run(cfg, strict=strict, extra=(drift.make_check(None),))
    return Health(initialised=True, findings=findings, last_run=last_agent_run(root))
