import re
import tomllib
from pathlib import Path
from string import Template

import pytest

from docforge import resources
from docforge.config import DEFAULT_DOCS, parse
from docforge.doctypes import DOC_TYPES, UNCERTAIN, UNCERTAIN_RE, render


def test_every_default_doc_has_a_type() -> None:
    typed = {d.path for d in DOC_TYPES}
    assert set(DEFAULT_DOCS) - {"CHANGELOG.md"} == typed


@pytest.mark.parametrize("doc", DOC_TYPES, ids=lambda d: d.path)
def test_render_contains_every_section(doc: object) -> None:
    from docforge.doctypes import DocType

    assert isinstance(doc, DocType)
    text = render(doc, "Demo")
    headings = re.findall(r"^## (.+)$", text, flags=re.M)
    assert tuple(headings) == doc.sections
    assert text.startswith("# ")
    assert UNCERTAIN in text


def test_uncertain_regex_accepts_dash_variants() -> None:
    for dash in ("-", "–", "—"):
        assert UNCERTAIN_RE.search(f"uncertain {dash} verify with developer")


@pytest.mark.parametrize(
    "name", ["adr-template.md", "CHANGELOG.md", "docforge.toml", "manual.yaml", "manual-header.tex", "docforge.yml"]
)
def test_static_templates_load(name: str) -> None:
    assert resources.read(name).strip()


def test_toml_template_renders_to_valid_config() -> None:
    text = Template(resources.read("docforge.toml")).substitute(name="demo", impact="")
    cfg = parse(tomllib.loads(text), Path("."))
    assert cfg.name == "demo"
    assert "docs/adr/[0-9]*.md" in cfg.manual_chapters


def test_adr_template_has_status_section() -> None:
    assert "## Status" in resources.read("adr-template.md")
