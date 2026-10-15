#!/usr/bin/env bash
# One-time Google Cloud free-tier provisioning for the single e2-micro deployment. Safe to re-run.
# Requires an authenticated gcloud owner of the project with billing linked.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/config.sh"
HERE="$LV_ROOT/ops/gcp"
exists() { "$@" >/dev/null 2>&1; }

g services enable compute.googleapis.com artifactregistry.googleapis.com

exists g compute networks describe lv-net ||
  g compute networks create lv-net --subnet-mode custom
exists g compute networks subnets describe lv-subnet --region "$LV_GCP_REGION" ||
  g compute networks subnets create lv-subnet --network lv-net --region "$LV_GCP_REGION" \
    --range 10.10.0.0/24 --enable-private-ip-google-access
# SSH only from the operator's current public IP; the operator listener is loopback-only.
exists g compute firewall-rules describe lv-allow-admin || bash "$HERE/allow-my-ip.sh"
# Public HTTPS (and HTTP for ACME challenges and redirects) terminates in Caddy.
exists g compute firewall-rules describe lv-allow-web ||
  g compute firewall-rules create lv-allow-web --network lv-net --direction INGRESS \
    --allow tcp:80,tcp:443,udp:443 --source-ranges 0.0.0.0/0 \
    --description "Public web: Caddy TLS and Let's Encrypt HTTP-01"

exists g iam service-accounts describe "$LV_GCP_SA" ||
  g iam service-accounts create lv-host --display-name "Launch visibility VM"

exists g artifacts repositories describe "$LV_GCP_REPO" --location "$LV_GCP_REGION" ||
  g artifacts repositories create "$LV_GCP_REPO" --repository-format docker \
    --location "$LV_GCP_REGION" --description "Launch visibility images (free tier: keep under 0.5 GB)"
g artifacts repositories set-cleanup-policies "$LV_GCP_REPO" --location "$LV_GCP_REGION" \
  --policy "$HERE/cleanup-policy.json" --no-dry-run >/dev/null
for attempt in 1 2 3 4 5 6; do
  # A new service account can take a few seconds to become visible to IAM.
  if g artifacts repositories add-iam-policy-binding "$LV_GCP_REPO" --location "$LV_GCP_REGION" \
    --member "serviceAccount:$LV_GCP_SA" --role roles/artifactregistry.reader >/dev/null; then
    break
  fi
  [ "$attempt" = 6 ] && exit 1
  sleep 10
done

exists g compute instances describe "$LV_GCP_VM" --zone "$LV_GCP_ZONE" ||
  g compute instances create "$LV_GCP_VM" --zone "$LV_GCP_ZONE" --machine-type e2-micro \
    --subnet lv-subnet --image-family debian-13 --image-project debian-cloud \
    --boot-disk-size 30GB --boot-disk-type pd-standard \
    --service-account "$LV_GCP_SA" --scopes cloud-platform \
    --shielded-secure-boot --shielded-vtpm --shielded-integrity-monitoring \
    --metadata enable-oslogin=TRUE --metadata-from-file startup-script="$HERE/vm-startup.sh"

# Ephemeral IP: no reservation to bill when the VM is stopped, but a stop/start changes it,
# so update the DNS A record afterwards.
g compute instances describe "$LV_GCP_VM" --zone "$LV_GCP_ZONE" \
  --format 'value(networkInterfaces[0].accessConfigs[0].natIP)' |
  sed 's/^/Public IPv4 for the DNS A record: /'

[ -f "$LV_STATE/vm.env" ] || python "$HERE/make_env.py" "$LV_STATE" "$LV_IMAGES" "$LV_PUBLIC_ORIGIN"
echo "Provisioned. Next: ops/gcp/deploy.sh"
