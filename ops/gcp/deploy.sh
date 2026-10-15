#!/usr/bin/env bash
# Build both images locally, push them to Artifact Registry and roll the VM's Compose stack.
# The VM environment comes from .runtime/gcp/vm.env (created by provision.sh; edit it there).
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/config.sh"

TAG=$(git -C "$LV_ROOT" rev-parse --short=12 HEAD)
[ -z "$(git -C "$LV_ROOT" status --porcelain)" ] || TAG="$TAG-dirty-$(date -u +%Y%m%d%H%M%S)"
[ -f "$LV_STATE/vm.env" ] || { echo "Missing $LV_STATE/vm.env; run ops/gcp/provision.sh" >&2; exit 1; }

# Empty registry/profile directories are Dockerfile inputs but are not tracked by git.
mkdir -p "$LV_ROOT/data/registry" "$LV_ROOT/data/profiles"
docker build -f "$LV_ROOT/ops/api.Dockerfile" -t "$LV_IMAGES/api:$TAG" "$LV_ROOT"
docker build -f "$LV_ROOT/ops/web.Dockerfile" -t "$LV_IMAGES/web:$TAG" "$LV_ROOT"
gcloud auth configure-docker "$LV_GCP_REGION-docker.pkg.dev" --quiet >/dev/null 2>&1
docker push --quiet "$LV_IMAGES/api:$TAG"
docker push --quiet "$LV_IMAGES/web:$TAG"

STAGE=$(mktemp -d)/lv-release
mkdir -p "$STAGE"
cp "$LV_ROOT/compose.yaml" "$LV_ROOT/ops/gcp/compose.gcp.yaml" "$LV_ROOT/ops/gcp/remote-deploy.sh" \
  "$LV_ROOT/ops/gcp/Caddyfile" "$LV_STATE/vm.env" "$STAGE/"
REMOTE="/tmp/lv-release-$TAG"
# SSH is admitted only from the allowlisted operator IP (ops/gcp/allow-my-ip.sh).
# plink/pscp on Windows cannot answer the first-connection host-key prompt.
SSH=(--zone "$LV_GCP_ZONE" --strict-host-key-checking=no)
g compute ssh "$LV_GCP_VM" "${SSH[@]}" --command "rm -rf $REMOTE && mkdir -p $REMOTE"
g compute scp --recurse "$STAGE"/* "$LV_GCP_VM:$REMOTE/" "${SSH[@]}"
rm -rf "$STAGE"
g compute ssh "$LV_GCP_VM" "${SSH[@]}" --command "sudo bash $REMOTE/remote-deploy.sh $TAG"
echo "Deployed $TAG to $LV_PUBLIC_ORIGIN (operator: ops/gcp/tunnel.sh, http://localhost:$LV_TUNNEL_PORT)"
