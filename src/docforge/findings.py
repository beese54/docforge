"""The Finding record every check emits, plus its JSON schema (the `--format json` contract)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import IntEnum
from typing import Any


class Severity(IntEnum):
    INFO = 0
    WARN = 1
    ERROR = 2

    def __str__(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    file: str
    message: str
    line: int | None = None
    category: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = str(self.severity)
        return data

    def to_text(self) -> str:
        loc = f"{self.file}:{self.line}" if self.line else self.file
        return f"{str(self.severity).upper():5} {self.rule:10} {loc}: {self.message}"


FINDING_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["rule", "severity", "file", "line", "message", "category"],
    "properties": {
        "rule": {"type": "string", "minLength": 1},
        "severity": {"enum": ["info", "warn", "error"]},
        "file": {"type": "string"},
        "line": {"type": ["integer", "null"], "minimum": 1},
        "message": {"type": "string", "minLength": 1},
        "category": {"type": ["string", "null"]},
    },
}

REPORT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "additionalProperties": False,
    "required": ["findings", "summary"],
    "properties": {
        "findings": {"type": "array", "items": FINDING_SCHEMA},
        "summary": {
            "type": "object",
            "additionalProperties": False,
            "required": ["error", "warn", "info"],
            "properties": {k: {"type": "integer", "minimum": 0} for k in ("error", "warn", "info")},
        },
    },
}
