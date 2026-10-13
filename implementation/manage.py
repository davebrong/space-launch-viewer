from __future__ import annotations

import argparse
import hashlib
import json
import secrets

from services.api.config import ROOT


def configure() -> None:
    path = ROOT / ".env"
    if path.exists():
        return
    password = secrets.token_urlsafe(32)
    content = (ROOT / ".env.example").read_text().replace("CHANGE_ME", password)
    path.write_text(content)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["configure", "admin-secret", "manifest", "migrate", "ingest"])
    args = parser.parse_args()
    if args.command == "configure":
        configure()
    elif args.command == "migrate":
        from alembic.config import Config
        from alembic import command

        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    elif args.command == "admin-secret":
        secret = secrets.token_urlsafe(48)
        print("Save this private admin secret: " + secret)
        print("ADMIN_SECRET_HASH=" + hashlib.sha256(secret.encode()).hexdigest())
    elif args.command == "ingest":
        from services.worker.ingestion import cycle
        from datetime import datetime, timezone

        cycle(datetime.now(timezone.utc))
    else:
        from importlib.metadata import distributions
        from packages.visibility.astronomy import model_manifest

        files = ["uv.lock", "package-lock.json", "data/gazetteer/census-2025.zip"]
        manifest = {
            "astronomy": model_manifest(),
            "files": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files},
            "dependencies": [
                {
                    "name": d.metadata["Name"],
                    "version": d.version,
                    "license": d.metadata.get("License-Expression")
                    or d.metadata.get("License")
                    or "See distribution license files",
                }
                for d in distributions()
            ],
        }
        (ROOT / "evidence/build/dependency-manifest.json").write_text(json.dumps(manifest, indent=2))
        print("Recorded package, asset and license manifest")


if __name__ == "__main__":
    main()
