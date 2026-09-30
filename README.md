# docforge

## Purpose

docforge is a command-line tool for keeping engineering documentation in a repository accurate ("docs-as-code"). It scaffolds a fixed documentation set, checks it deterministically (structure, sections, links, ADRs, drift between code and docs), runs an AI agent inside a sandbox to *propose* documentation patches, and builds the Markdown into a versioned PDF manual.

Design background lives in `specification.json` and `definition_of_done.md` (not reviewed while writing these docs: uncertain — verify with developer).

<!-- sources: pyproject.toml, src/docforge/cli.py, README.md (previous version) -->

## Technologies

- Python 3.12+, [Typer](https://typer.tiangolo.com/) for the CLI, the `anthropic` SDK for the agent, built with hatchling and managed with `uv`.
- External tools for the PDF manual: pandoc, tectonic (LaTeX), mermaid-cli (`mmdc`).
- OpenShell and Docker for the agent and build sandboxes.
- Dev tooling declared: pytest, ruff, mypy (strict), jsonschema.

See [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md).

<!-- sources: pyproject.toml, init.sh, sandbox/build.Dockerfile -->

## Architecture at a Glance

Commands: `init`, `check`, `build`, `agent {impact,adr,bootstrap}`, `apply`, `usage`. The agent can only read the repository and *stage* Markdown writes; a human reviews `docforge.patch` and `docforge apply` commits it to a new branch. CI runs only the deterministic `check`; the model is never called in CI. Details in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

<!-- sources: src/docforge/cli.py, .github/workflows/docforge.yml -->

## Prerequisites

Run `./init.sh` (Linux/WSL). It reports, and does not install, missing: python3 3.12+, uv, git, pandoc, tectonic, Node >= 20, mmdc, pdftotext (poppler-utils), docker, openshell. It then runs `uv sync`.

<!-- sources: init.sh -->

## Local Development

```bash
./init.sh            # check prerequisites + create the venv (default ~/.venvs/docforge)
./dev.sh docforge check      # run any command in the dev environment
./dev.sh ruff check src tests
./dev.sh mypy src
```

`dev.sh` is `uv run` with `UV_PROJECT_ENVIRONMENT` pointed at the venv outside the repo. Model calls need `ANTHROPIC_API_KEY` (or the OpenShell provider); see [docs/MAINTENANCE.md](docs/MAINTENANCE.md).

<!-- sources: dev.sh, init.sh, pyproject.toml -->

## Running Tests

```bash
./dev.sh pytest -q
```

See [docs/TESTING.md](docs/TESTING.md).

<!-- sources: dev.sh, pyproject.toml, tests/conftest.py -->

## Deployment

docforge is not a deployed service. It is installed as a Python wheel; CI installs it with `uvx` from a git URL, and the sandbox images are built by `sandbox/build-images.sh`. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

<!-- sources: .github/workflows/docforge.yml, sandbox/build-images.sh -->

## Documentation

- [Architecture](docs/ARCHITECTURE.md), [Design](docs/DESIGN.md), [How it works](docs/HOW_IT_WORKS.md)
- [Data model](docs/DATA_MODEL.md), [API / CLI](docs/API.md), [Security](docs/SECURITY.md)
- [Deployment](docs/DEPLOYMENT.md), [Testing](docs/TESTING.md), [Operations](docs/OPERATIONS.md), [Maintenance](docs/MAINTENANCE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md), [Dependencies](docs/DEPENDENCIES.md)
- Decisions: [docs/adr/](docs/adr/001-human-reviewed-patches-only.md)
- [CHANGELOG](CHANGELOG.md)

<!-- sources: docforge.toml -->
