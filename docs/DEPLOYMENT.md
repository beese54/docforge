# Deployment

> How the system is built, configured and deployed, and how to roll back.

## Environments

- **Developer machine** (Linux/WSL): venv managed by `uv`, default `~/.venvs/docforge` ([README](../README.md)).
- **CI**: GitHub Actions on `ubuntu-24.04`, workflow `docforge`.
- **Sandboxes**: OpenShell sandboxes from two Docker images (agent, build).
- Staging/production: not applicable; there is no hosted service (uncertain — verify with developer whether any distribution channel such as PyPI is planned).

<!-- sources: init.sh, .github/workflows/docforge.yml, sandbox/build-images.sh -->

## Build

- Wheel: `uv build --wheel` (hatchling; package `src/docforge`). Version is in `pyproject.toml` (0.1.0).
- Images: `sandbox/build-images.sh` removes `dist/`, builds the wheel, then builds `docforge-agent:<version>` (python:3.12-slim, git, curl, the wheel, non-root `sandbox` user) and `docforge-build:<version>` (ubuntu:24.04, pandoc, tectonic, Node 22, mermaid-cli 11, headless Chrome, and a warm-up build of `sandbox/warmup` so builds work offline).
- The build image downloads tectonic via an install script from `drop-sh.fullyjustified.net` at build time, without a checksum (Node is checksum-verified).

<!-- sources: pyproject.toml, sandbox/build-images.sh, sandbox/agent.Dockerfile, sandbox/build.Dockerfile -->

## Deploy

There is nothing to deploy to a server.

- **CI check:** on pull requests and pushes to `main`/`master`, `uvx --from "$DOCFORGE_SPEC" docforge check --strict --base <ref>`. `DOCFORGE_SPEC` is `docforge @ git+https://github.com/beese54/docforge`; that repository has been public since 2026-09-30 (first green runs: docforge `main` push and markdown-visualiser PR #1). Pin `DOCFORGE_SPEC` to a tag once releases exist.
- **CI manual job:** on manual dispatch or tag refs, installs pandoc, tectonic and mermaid-cli, runs `docforge build`, uploads `documentation/build/*.pdf` as artifact `manual`.
- **Agent:** `sandbox/run-agent.sh` (needs the images, the imported `anthropic` provider profile and an OpenShell gateway). Setup of the profile: see the header of `sandbox/anthropic-profile.yaml`. The script ships the repository as a tar (directory uploads drop `.git`), sets `DOCFORGE_PROGRESS=1` inside the sandbox so each trace line streams out as it happens, and copies the usage ledger in and out.
- **Native Docker engine (WSL with Docker Desktop):** `sudo sandbox/install-native-docker.sh` installs Docker's static binaries in `/opt/docker-openshell`, a systemd service `docker-openshell` on `/run/docker-openshell.sock` with its own data root (`/var/lib/docker-openshell`) and bridge ranges (172.30/172.31). Docker Desktop is untouched. OpenShell uses it through `~/.config/openshell/gateway.toml` (`[openshell.drivers.docker] socket_path`). `--uninstall` removes it. It is needed because Docker Desktop's host network cannot reach the gateway on the distro's 127.0.0.1.
- **Console:** `pip install 'docforge[console]'` (or `uv sync --all-extras`), then `docforge serve` from the docforge checkout so it can find `sandbox/`. Only 127.0.0.1 is served; open the printed link in a browser on the same machine. For the Push and Open PR buttons in WSL: `git config --global credential.helper "/mnt/c/Program\ Files/Git/mingw64/bin/git-credential-manager.exe"`, and `gh` (the Windows `gh.exe` is used automatically).

<!-- sources: .github/workflows/docforge.yml, STATUS-2026-09-30.md, sandbox/run-agent.sh, sandbox/anthropic-profile.yaml, sandbox/install-native-docker.sh, src/docforge/cli.py, src/docforge/console/publish.py -->

## Configuration

See [DESIGN.md](DESIGN.md#configuration-strategy) for `docforge.toml`. Deployment-relevant settings: `DOCFORGE_SPEC` (CI), `DOCFORGE_HOME`, `ANTHROPIC_API_KEY` (agent), image tags derived from `pyproject.toml` version. The build sandbox needs `XDG_CACHE_HOME=/opt/cache`, `PUPPETEER_CACHE_DIR=/opt/cache/puppeteer`, `DOCFORGE_PUPPETEER_CONFIG=/opt/docforge/puppeteer.json` passed explicitly because OpenShell exec sessions do not inherit image ENV.

<!-- sources: .github/workflows/docforge.yml, sandbox/build-policy.yaml, sandbox/build.Dockerfile -->

## Rollback

No release process is defined in the repository (uncertain — verify with developer). Practical options: pin `DOCFORGE_SPEC` to an earlier git tag or commit; rebuild images from an earlier commit (image tags equal the version, so rebuilding overwrites a tag unless the version is bumped). Doc patches applied by `docforge apply` are ordinary commits on their own branch and can be dropped by deleting the branch or reverting.

<!-- sources: .github/workflows/docforge.yml, sandbox/build-images.sh, src/docforge/apply.py -->
