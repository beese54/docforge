# docforge PDF build image: pandoc + tectonic + mermaid-cli, with every download done at image build time so
# `docforge build` runs with NO network (sandbox/build-policy.yaml grants none). Build from the repo root:
#   uv build --wheel && docker build -f sandbox/build.Dockerfile -t docforge-build:0.1.0 .
FROM ubuntu:24.04

ARG NODE_MAJOR=22
ENV DEBIAN_FRONTEND=noninteractive \
    XDG_CACHE_HOME=/opt/cache \
    PUPPETEER_CACHE_DIR=/opt/cache/puppeteer \
    DOCFORGE_PUPPETEER_CONFIG=/opt/docforge/puppeteer.json \
    PATH=/opt/docforge/venv/bin:/opt/node/bin:$PATH

# pandoc 3.1.3 (Ubuntu 24.04), fonts, PDF tools, and the shared libraries headless Chromium needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        pandoc poppler-utils git curl ca-certificates xz-utils unzip python3 python3-venv \
        fonts-dejavu fonts-liberation libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libxkbcommon0 \
        libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 \
    && rm -rf /var/lib/apt/lists/*

# Tectonic (single binary).
RUN cd /usr/local/bin && curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh \
    && tectonic --version

# Node LTS + mermaid-cli + its headless Chrome, checksum-verified.
RUN V=$(curl -fsSL https://nodejs.org/dist/index.json | python3 -c "import json,sys; print(next(r['version'] for r in json.load(sys.stdin) if r['version'].startswith('v${NODE_MAJOR}.')))") \
    && cd /tmp && curl -fsSLO https://nodejs.org/dist/$V/node-$V-linux-x64.tar.xz \
    && curl -fsSL https://nodejs.org/dist/$V/SHASUMS256.txt | grep " node-$V-linux-x64.tar.xz\$" | sha256sum -c - \
    && mkdir -p /opt/node && tar -xJf node-$V-linux-x64.tar.xz -C /opt/node --strip-components=1 && rm node-*.tar.xz \
    && npm install -g --silent @mermaid-js/mermaid-cli@11 \
    && cd /opt/node/lib/node_modules/@mermaid-js/mermaid-cli \
    && ./node_modules/.bin/puppeteer browsers install chrome-headless-shell

# docforge itself.
COPY dist/docforge-*.whl /tmp/
RUN python3 -m venv /opt/docforge/venv && /opt/docforge/venv/bin/pip install --no-cache-dir /tmp/docforge-*.whl \
    && rm /tmp/docforge-*.whl \
    && printf '{"args": ["--no-sandbox", "--no-zygote", "--disable-dev-shm-usage"]}\n' > /opt/docforge/puppeteer.json
# --no-zygote: Chromium's zygote creates a user namespace, which OpenShell's seccomp filter (rightly) forbids.

# Warm every cache offline builds need: render a fixture manual once (LaTeX packages, fonts, Chromium).
COPY sandbox/warmup /opt/docforge/warmup
RUN cd /opt/docforge/warmup && git init -q && git -c user.name=w -c user.email=w@w add -A \
    && git -c user.name=w -c user.email=w@w commit -qm warmup && docforge build --strict \
    && rm -rf documentation/build .git \
    && chmod -R a+rX /opt/cache

RUN userdel -r ubuntu 2>/dev/null; groupadd --gid 1000 sandbox && useradd --uid 1000 --gid sandbox --create-home sandbox \
    && install -d -o sandbox -g sandbox /sandbox
WORKDIR /sandbox
USER sandbox
RUN git config --global --add safe.directory '*'
