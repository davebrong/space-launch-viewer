#!/usr/bin/env bash
# Operator access (no public port): forwards http://localhost:13080 to the VM's loopback-only
# proxy listener over SSH. This origin is on the API allow-list (see make_env.py). Ctrl+C to stop.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/config.sh"
exec gcloud compute ssh "$LV_GCP_VM" --zone "$LV_GCP_ZONE" --strict-host-key-checking=no \
  -- -N -L "$LV_TUNNEL_PORT:127.0.0.1:3080"
