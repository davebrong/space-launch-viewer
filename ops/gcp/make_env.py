"""Create the private VM environment file for the Google Cloud deployment (never committed).

Usage: python ops/gcp/make_env.py <output-dir> <image-repo> <public-origin>
Writes <output-dir>/vm.env and <output-dir>/admin-secret.txt once; refuses to overwrite.
"""

from __future__ import annotations

import hashlib
import secrets
import sys
from pathlib import Path


def main() -> None:
    out, repo, public = Path(sys.argv[1]), sys.argv[2], sys.argv[3].rstrip("/")
    env, secret_file = out / "vm.env", out / "admin-secret.txt"
    if env.exists() or secret_file.exists():
        sys.exit(f"{out} already holds a VM environment; edit it instead of regenerating")
    out.mkdir(parents=True, exist_ok=True)
    admin = secrets.token_urlsafe(48)
    lines = [
        "# Private. Source of truth for /opt/launch-visibility/.env; deploy.sh installs it on each release.",
        "POSTGRES_PASSWORD=" + secrets.token_urlsafe(32),
        # Public hostname first; the second origin is the SSH operator tunnel (ops/gcp/tunnel.sh).
        f"COMPOSE_APP_ORIGIN={public},http://localhost:13080",
        "COOKIE_SECURE=true",
        "ADMIN_SECRET_HASH=" + hashlib.sha256(admin.encode()).hexdigest(),
        f"LV_USER_AGENT=launch-visibility/0.1 (+{public})",
        "LV_IMAGE_REPO=" + repo,
        # Caddy obtains the certificate for this hostname; DNS must point at the VM's static IP.
        "LV_SITE_ADDRESS=" + public.split("://", 1)[-1],
    ]
    env.write_text("\n".join(lines) + "\n")
    secret_file.write_text(admin + "\n")
    for path in (env, secret_file):
        try:
            path.chmod(0o600)
        except OSError:
            pass
    print(f"Wrote {env} and {secret_file}")


if __name__ == "__main__":
    main()
