#!/usr/bin/env bash
# Run `docforge agent <task>` for a repository inside an OpenShell sandbox, then bring back the patch/report.
#   sandbox/run-agent.sh <repo-path> impact [--base REF]
#   sandbox/run-agent.sh <repo-path> bootstrap
#   sandbox/run-agent.sh <repo-path> adr "Title" [--note "..."]
# The API key never enters the sandbox: the `anthropic` provider supplies a placeholder that OpenShell swaps
# for the real key only on requests to api.anthropic.com. The usage ledger is carried in and out so the
# monthly budget cap spans sandbox runs.
#
set -euo pipefail

REPO=$(cd "$1" && pwd); shift
TASK=$1; shift
HERE=$(cd "$(dirname "$0")" && pwd)
VERSION=$(sed -n 's/^version = "\(.*\)"/\1/p' "$HERE/../pyproject.toml")
NAME="dfa-$(date +%s)"  # OpenShell names are max 19 chars
LEDGER="${DOCFORGE_HOME:-$HOME/.docforge}/usage.jsonl"
OUT="$REPO/documentation/build/agent"
STAGE=$(mktemp -d)
trap 'openshell sandbox delete "$NAME" >/dev/null 2>&1 || true; rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/out/home"
[ -f "$LEDGER" ] && cp "$LEDGER" "$STAGE/out/home/usage.jsonl"

openshell sandbox create --name "$NAME" --from "docforge-agent:$VERSION" \
  --policy "$HERE/agent-policy.yaml" --provider anthropic --detach -- sleep infinity
# Directory uploads are git-filtered and drop .git, which the agent needs for its diff. Ship the working tree
# (untracked files included) plus .git as one tar and unpack it inside. An uploaded directory lands under the
# destination by name: in -> /sandbox/in, out -> /sandbox/out.
REPO_IN="/sandbox/$(basename "$REPO")"
mkdir -p "$STAGE/in"
tar -C "$(dirname "$REPO")" --exclude=node_modules --exclude=documentation/build \
  -cf "$STAGE/in/repo.tar" "$(basename "$REPO")"
openshell sandbox upload "$NAME" "$STAGE/in" /sandbox </dev/null
openshell sandbox upload "$NAME" "$STAGE/out" /sandbox </dev/null
openshell sandbox exec --name "$NAME" -- sh -c 'tar -xf /sandbox/in/repo.tar -C /sandbox && rm -rf /sandbox/in' \
  </dev/null

set +e
openshell sandbox exec --name "$NAME" --workdir "$REPO_IN" \
  --env DOCFORGE_HOME=/sandbox/out/home --env GIT_OPTIONAL_LOCKS=0 \
  -- docforge agent "$TASK" "$@" --out /sandbox/out </dev/null  # exec waits for stdin EOF
status=$?
set -e

rm -rf "$STAGE/back" && mkdir -p "$STAGE/back"
openshell sandbox download "$NAME" /sandbox/out "$STAGE/back" </dev/null
src="$STAGE/back"; [ -d "$STAGE/back/out" ] && src="$STAGE/back/out"
if [ -f "$src/home/usage.jsonl" ]; then mkdir -p "$(dirname "$LEDGER")"; cp "$src/home/usage.jsonl" "$LEDGER"; fi
mkdir -p "$OUT"
for f in docforge.patch report.md policy.log run.json; do [ -f "$src/$f" ] && cp "$src/$f" "$OUT/"; done

echo "sandbox exit: $status   outputs: $OUT"
[ "$status" -eq 0 ] && echo "Review $OUT/report.md, then: docforge apply $OUT/docforge.patch --path $REPO"
exit "$status"
