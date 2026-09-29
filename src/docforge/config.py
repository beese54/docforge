"""Load and validate `docforge.toml`. Unknown keys are errors so typos never silently disable a check."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_NAME = "docforge.toml"

DEFAULT_DOCS: tuple[str, ...] = (
    "README.md",
    "CHANGELOG.md",
    "docs/ARCHITECTURE.md",
    "docs/DESIGN.md",
    "docs/HOW_IT_WORKS.md",
    "docs/DEPLOYMENT.md",
    "docs/MAINTENANCE.md",
    "docs/TROUBLESHOOTING.md",
    "docs/SECURITY.md",
    "docs/TESTING.md",
    "docs/DATA_MODEL.md",
    "docs/API.md",
    "docs/DEPENDENCIES.md",
    "docs/OPERATIONS.md",
)

# The only paths the agent (and `docforge apply`) may ever write. Deliberately not configurable.
AGENT_WRITABLE: tuple[str, ...] = ("README.md", "CHANGELOG.md", "docs/**")

DEFAULT_PER_RUN_USD: dict[str, float] = {"impact": 0.50, "adr": 0.30, "bootstrap": 3.00}
DEFAULT_MONTHLY_USD = 10.00


class ConfigError(Exception):
    """docforge.toml is missing, malformed or fails validation."""


@dataclass(frozen=True)
class ImpactRule:
    category: str
    globs: tuple[str, ...]
    docs: tuple[str, ...]
    adr_worthy: bool = False


@dataclass(frozen=True)
class Budget:
    per_run_usd: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PER_RUN_USD))
    monthly_usd: float = DEFAULT_MONTHLY_USD


@dataclass(frozen=True)
class Config:
    root: Path
    name: str
    manual_title: str
    required_docs: tuple[str, ...]
    impact: tuple[ImpactRule, ...]
    manual_chapters: tuple[str, ...]
    budget: Budget
    max_uncertain: int | None = None


_ALLOWED: dict[str, set[str]] = {
    "": {"project", "docs", "impact", "manual", "budget", "uncertain"},
    "project": {"name", "manual_title"},
    "docs": {"required"},
    "impact": {"category", "globs", "docs", "adr_worthy"},
    "manual": {"chapters"},
    "budget": {"per_run_usd", "monthly_usd"},
    "uncertain": {"max_markers"},
}


def _check_keys(table: dict[str, Any], section: str) -> None:
    unknown = set(table) - _ALLOWED[section]
    if unknown:
        where = f"[{section}]" if section else "top level"
        raise ConfigError(f"unknown key(s) at {where}: {', '.join(sorted(unknown))}")


def _str_list(value: Any, where: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
        raise ConfigError(f"{where} must be a non-empty list of non-empty strings")
    return tuple(value)


def _positive(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise ConfigError(f"{where} must be a positive number")
    return float(value)


def load(root: Path) -> Config:
    path = root / CONFIG_NAME
    if not path.is_file():
        raise ConfigError(f"{CONFIG_NAME} not found in {root} (run `docforge init`)")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{CONFIG_NAME}: {exc}") from exc
    return parse(data, root)


def parse(data: dict[str, Any], root: Path) -> Config:
    _check_keys(data, "")
    project = data.get("project", {})
    _check_keys(project, "project")
    name = project.get("name")
    if not isinstance(name, str) or not name:
        raise ConfigError("[project] name is required")
    manual_title = project.get("manual_title", f"{name} Technical Manual")
    if not isinstance(manual_title, str):
        raise ConfigError("[project] manual_title must be a string")

    docs = data.get("docs", {})
    _check_keys(docs, "docs")
    required = _str_list(docs["required"], "[docs] required") if "required" in docs else DEFAULT_DOCS

    rules: list[ImpactRule] = []
    seen: set[str] = set()
    for i, raw in enumerate(data.get("impact", [])):
        _check_keys(raw, "impact")
        where = f"[[impact]] #{i + 1}"
        category = raw.get("category")
        if not isinstance(category, str) or not category:
            raise ConfigError(f"{where}: category is required")
        if category in seen:
            raise ConfigError(f"{where}: duplicate category '{category}'")
        seen.add(category)
        adr = raw.get("adr_worthy", False)
        if not isinstance(adr, bool):
            raise ConfigError(f"{where}: adr_worthy must be true/false")
        rules.append(
            ImpactRule(
                category=category,
                globs=_str_list(raw.get("globs"), f"{where} globs"),
                docs=_str_list(raw.get("docs"), f"{where} docs"),
                adr_worthy=adr,
            )
        )

    manual = data.get("manual", {})
    _check_keys(manual, "manual")
    chapters = _str_list(manual["chapters"], "[manual] chapters") if "chapters" in manual else required

    budget_raw = data.get("budget", {})
    _check_keys(budget_raw, "budget")
    per_run = dict(DEFAULT_PER_RUN_USD)
    for key, value in budget_raw.get("per_run_usd", {}).items():
        per_run[key] = _positive(value, f"[budget.per_run_usd] {key}")
    monthly = _positive(budget_raw.get("monthly_usd", DEFAULT_MONTHLY_USD), "[budget] monthly_usd")

    uncertain = data.get("uncertain", {})
    _check_keys(uncertain, "uncertain")
    max_markers = uncertain.get("max_markers")
    if max_markers is not None and (
        isinstance(max_markers, bool) or not isinstance(max_markers, int) or max_markers < 0
    ):
        raise ConfigError("[uncertain] max_markers must be a non-negative integer")

    return Config(
        root=root,
        name=name,
        manual_title=manual_title,
        required_docs=required,
        impact=tuple(rules),
        manual_chapters=chapters,
        budget=Budget(per_run_usd=per_run, monthly_usd=monthly),
        max_uncertain=max_markers,
    )
