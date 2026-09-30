# docforge agent sandbox image. Build from the repo root:
#   sandbox/build-images.sh   (tags docforge-agent:<version from pyproject.toml>)
# Egress is decided by OpenShell policy (sandbox/agent-policy.yaml), not by this image. The API key is never
# baked in: the attached `anthropic` provider supplies a placeholder that OpenShell swaps at egress.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY dist/docforge-*.whl /tmp/
RUN pip install --no-cache-dir /tmp/docforge-*.whl && rm /tmp/docforge-*.whl

RUN groupadd --gid 1000 sandbox && useradd --uid 1000 --gid sandbox --create-home sandbox \
    && install -d -o sandbox -g sandbox /sandbox /sandbox/out
WORKDIR /sandbox
USER sandbox
# Uploaded repos are owned by the sandbox user; git refuses "dubious ownership" otherwise.
RUN git config --global --add safe.directory '*'
