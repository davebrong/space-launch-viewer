#!/bin/bash
# Runs on the VM (as root, via ops/gcp/deploy.sh): install the staged release and roll the stack.
# Usage: remote-deploy.sh <image-tag>
set -euo pipefail
TAG=$1
STAGE=$(cd "$(dirname "$0")" && pwd)
APP=/opt/launch-visibility

# First boot: the startup script may still be installing Docker.
for _ in $(seq 60); do docker compose version >/dev/null 2>&1 && break; sleep 10; done
docker compose version >/dev/null

install -d -m 0750 "$APP"
# Caddy (uid 1000) keeps its ACME account and certificates here across restarts.
install -d -o 1000 -g 1000 -m 0700 "$APP/caddy-data"
install -m 0644 "$STAGE/compose.yaml" "$APP/compose.yaml"
install -m 0644 "$STAGE/compose.gcp.yaml" "$APP/compose.gcp.yaml"
install -m 0644 "$STAGE/Caddyfile" "$APP/Caddyfile.gcp"
install -m 0600 "$STAGE/vm.env" "$APP/.env"
printf 'LV_IMAGE_TAG=%s\nCOMPOSE_FILE=compose.yaml:compose.gcp.yaml\n' "$TAG" >> "$APP/.env"
rm -rf "$STAGE"

# Short-lived VM service-account token; the account only has Artifact Registry read access.
TOKEN=$(curl -fsS -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["access_token"])')
REGISTRY=$(sed -n 's/^LV_IMAGE_REPO=\([^/]*\)\/.*/\1/p' "$APP/.env")
docker login -u oauth2accesstoken --password-stdin "https://$REGISTRY" <<<"$TOKEN" >/dev/null

cd "$APP"
docker compose pull --quiet
docker compose up -d --no-build --wait --wait-timeout 600 --remove-orphans
docker image prune -af >/dev/null
docker compose ps --format 'table {{.Service}}\t{{.Status}}'
