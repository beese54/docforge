#!/usr/bin/env bash
# Install a separate, native Docker engine inside this WSL distro for OpenShell sandboxes only.
#
# Why: OpenShell 0.1.2's Docker driver runs each sandbox's supervisor on the "host network" and dials the
# gateway at 127.0.0.1:17670. Docker Desktop's host network is its own VM, so that address never reaches the
# gateway running in this distro. A native engine here shares this distro's network, so it does.
#
# What it installs (Docker Desktop is not touched):
#   /opt/docker-openshell/bin/          official static Docker binaries (download.docker.com)
#   /etc/systemd/system/docker-openshell.service
#   /run/docker-openshell.sock          socket, group "docker"
#   /var/lib/docker-openshell           images/containers for this engine only
#   bridge 172.31.0.0/16, pools 172.30.0.0/16 (chosen not to collide with Docker Desktop)
#
# Usage:  sudo sandbox/install-native-docker.sh            # install / upgrade
#         sudo sandbox/install-native-docker.sh --uninstall
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
UNIT=/etc/systemd/system/docker-openshell.service
SOCK=/run/docker-openshell.sock

if [ "${1:-}" = "--uninstall" ]; then
  systemctl disable --now docker-openshell.service 2>/dev/null || true
  rm -f "$UNIT" && systemctl daemon-reload
  rm -rf /opt/docker-openshell /var/lib/docker-openshell /run/docker-openshell "$SOCK"
  echo "docker-openshell removed."
  exit 0
fi

command -v iptables >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iptables; }
getent group docker >/dev/null || groupadd docker

BASE=https://download.docker.com/linux/static/stable/x86_64
VERSION=$(curl -fsSL "$BASE/" | grep -oE 'docker-[0-9]+\.[0-9]+\.[0-9]+\.tgz' | sort -V | tail -1)
echo "Installing $VERSION into /opt/docker-openshell"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
curl -fsSL --proto '=https' "$BASE/$VERSION" -o "$TMP/docker.tgz"
tar -xzf "$TMP/docker.tgz" -C "$TMP"
systemctl stop docker-openshell.service 2>/dev/null || true
rm -rf /opt/docker-openshell/bin
mkdir -p /opt/docker-openshell
mv "$TMP/docker" /opt/docker-openshell/bin

cat > "$UNIT" <<'UNIT'
[Unit]
Description=Native Docker engine for OpenShell sandboxes (separate from Docker Desktop)
After=network-online.target
Wants=network-online.target

[Service]
Environment=PATH=/opt/docker-openshell/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/opt/docker-openshell/bin/dockerd -H unix:///run/docker-openshell.sock --group docker \
  --data-root /var/lib/docker-openshell --exec-root /run/docker-openshell \
  --pidfile /run/docker-openshell.pid --bip 172.31.0.1/16 \
  --default-address-pool base=172.30.0.0/16,size=24
Restart=on-failure
Delegate=yes
KillMode=process
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now docker-openshell.service
for _ in $(seq 1 20); do [ -S "$SOCK" ] && break; sleep 1; done
/opt/docker-openshell/bin/docker -H "unix://$SOCK" version --format 'docker-openshell server {{.Server.Version}}: OK'
echo "Done. Now tell Claude \"installed\"; it will point OpenShell at $SOCK."
