#!/bin/bash
# Compute Engine startup script for the free-tier e2-micro host. Idempotent; runs on every boot.
# Installs Docker Engine + Compose from Docker's apt repository, adds swap for the 1 GB VM,
# and caps container log size. Application files arrive separately via ops/gcp/deploy.sh.
set -euo pipefail

if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  [ -f /swapfile ] || { fallocate -l 2G /swapfile; chmod 600 /swapfile; mkswap /swapfile; }
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness=10' > /etc/sysctl.d/90-launch-visibility.conf
sysctl -q -p /etc/sysctl.d/90-launch-visibility.conf

if ! command -v docker >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -q
  apt-get install -y -q ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

mkdir -p /etc/docker
if [ ! -f /etc/docker/daemon.json ]; then
  echo '{"log-driver": "local", "log-opts": {"max-size": "10m", "max-file": "3"}}' > /etc/docker/daemon.json
  systemctl restart docker
fi
systemctl enable --now docker

install -d -m 0750 /opt/launch-visibility /opt/launch-visibility/ops
