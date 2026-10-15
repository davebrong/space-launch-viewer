#!/usr/bin/env bash
# Point the operator SSH firewall rule at this machine's current public IPv4 (or the CIDR given as
# $1). Run it after your ISP changes your address; it uses the Compute API, not SSH.
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/config.sh"
CIDR=${1:-"$(curl -4 -fsS https://checkip.amazonaws.com | tr -d '[:space:]')/32"}
if g compute firewall-rules describe lv-allow-admin >/dev/null 2>&1; then
  g compute firewall-rules update lv-allow-admin --source-ranges "$CIDR"
else
  g compute firewall-rules create lv-allow-admin --network lv-net --direction INGRESS \
    --allow tcp:22 --source-ranges "$CIDR" \
    --description "Operator SSH from the allowlisted public IP only (ops/gcp/allow-my-ip.sh)"
fi
echo "SSH allowed from $CIDR only"
