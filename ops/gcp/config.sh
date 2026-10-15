# Shared settings for ops/gcp/*.sh (sourced). Override any value from the environment.
# Free tier (per billing account, not per project): one e2-micro in us-west1, us-central1 or
# us-east1 with <=30 GB standard disk.

# Git Bash on Windows: give native tools (docker, gcloud) mixed-style local paths (N:/...).
native_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
LV_ROOT=$(native_path "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)")
LV_STATE="$LV_ROOT/.runtime/gcp"

# Operator identity lives only in the gitignored .runtime/gcp/config.local.sh:
#   LV_GCP_PROJECT=<project id>
#   LV_GCP_ACCOUNT=<gcloud account>
#   LV_PUBLIC_ORIGIN=https://<public hostname>
# shellcheck source=/dev/null
[ -f "$LV_STATE/config.local.sh" ] && . "$LV_STATE/config.local.sh"
: "${LV_GCP_PROJECT:?Set LV_GCP_PROJECT in .runtime/gcp/config.local.sh}"
: "${LV_GCP_ACCOUNT:?Set LV_GCP_ACCOUNT in .runtime/gcp/config.local.sh}"
: "${LV_PUBLIC_ORIGIN:?Set LV_PUBLIC_ORIGIN in .runtime/gcp/config.local.sh}"

LV_GCP_REGION=${LV_GCP_REGION:-us-central1}
LV_GCP_ZONE=${LV_GCP_ZONE:-us-central1-c}
LV_GCP_VM=${LV_GCP_VM:-launch-visibility}
LV_GCP_REPO=${LV_GCP_REPO:-launch-visibility}
LV_TUNNEL_PORT=${LV_TUNNEL_PORT:-13080}

LV_GCP_SA="lv-host@${LV_GCP_PROJECT}.iam.gserviceaccount.com"
LV_IMAGES="${LV_GCP_REGION}-docker.pkg.dev/${LV_GCP_PROJECT}/${LV_GCP_REPO}"

# Pin account and project per process; the user's global gcloud configuration is left untouched.
export CLOUDSDK_CORE_ACCOUNT="$LV_GCP_ACCOUNT" CLOUDSDK_CORE_PROJECT="$LV_GCP_PROJECT"
g() { gcloud --quiet "$@"; }
