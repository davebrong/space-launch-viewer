"""Encrypted logical backup with consistent database snapshot and immutable file hashes.

Restore refuses a populated destination. Off-host evidence is distinct from a local drill.
The latest deletion ledger MUST be supplied independently of the old backup.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import DateTime, select, delete, func
from sqlalchemy.dialects.postgresql import insert

from services.api import db
from services.api.config import DATA, ROOT
from packages.visibility.common import stamp, utc


def apply_tombstones(conn, tombstones: list[dict]) -> int:
    removed = 0
    for row in tombstones:
        conn.execute(delete(db.cache).where(db.cache.c.key.like("assessment:" + row["id"] + ":%")))
        for table in (db.sessions, db.locations, db.subscriptions):
            removed += conn.execute(delete(table).where(table.c.id == row["id"])).rowcount
        conn.execute(
            insert(db.ledger).values(id=row["id"], deleted_at=utc(row["deleted_at"])).on_conflict_do_nothing()
        )
    # Point lookups are rehydrated only for surviving locations; no orphaned GPS cache.
    conn.execute(delete(db.cache).where(db.cache.c.key.like("point:%")))
    conn.execute(delete(db.cache).where(db.cache.c.key.like("downgrade:%")))
    # No ambiguous or overdue work is automatically redelivered after restore.
    from sqlalchemy import update

    conn.execute(
        update(db.outbox)
        .where(db.outbox.c.state.in_(["pending", "claimed", "retry", "delivery_unknown"]))
        .values(state="cancelled", lease_until=None)
    )
    return removed


def capture(key: bytes) -> bytes:
    at = datetime.now(timezone.utc)
    tables = {}
    with db.engine().connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            for table in db.metadata.sorted_tables:
                tables[table.name] = [
                    {k: stamp(v) if isinstance(v, datetime) else v for k, v in row.items()}
                    for row in conn.execute(select(table)).mappings()
                ]
    files = {}
    for folder in (
        ROOT / "data/gazetteer",
        ROOT / "data/registry",
        ROOT / "data/profiles",
        DATA / "snapshots",
    ):
        if folder.exists():
            for path in folder.rglob("*"):
                if path.is_file():
                    files[folder.name + "/" + str(path.relative_to(folder)).replace("\\", "/")] = (
                        path.read_bytes()
                    )
    manifest = {
        "schema_revision": "0002",
        "created_at": stamp(at),
        "tables": tables,
        "assets": {name: hashlib.sha256(body).hexdigest() for name, body in files.items()},
        "restore_delivery_disabled": True,
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("database.json", json.dumps(manifest, allow_nan=False))
        for name, body in files.items():
            archive.writestr("assets/" + name, body)
    return Fernet(key).encrypt(stream.getvalue())


def restore(payload: bytes, key: bytes, latest_tombstones: list[dict], asset_destination: Path) -> dict:
    decoded = Fernet(key).decrypt(payload)
    with zipfile.ZipFile(io.BytesIO(decoded)) as archive:
        manifest = json.loads(archive.read("database.json"))
        if manifest["schema_revision"] not in ("0001", "0002"):
            raise ValueError("Unsupported backup schema")
        content = {}
        for name, sha in manifest["assets"].items():
            path = (asset_destination / name).resolve()
            if not path.is_relative_to(asset_destination.resolve()):
                raise ValueError("Unsafe archive path")
            body = archive.read("assets/" + name)
            if hashlib.sha256(body).hexdigest() != sha:
                raise ValueError("Asset hash mismatch")
            content[path] = body
    # Rehydrate NWS point lookups after restore, never resurrect GPS-bearing raw blobs.
    point_hashes = {
        r["sha256"]
        for r in manifest["tables"]["provider_snapshots"]
        if r["body"].get("source_url", "").startswith("https://api.weather.gov/points/")
    }
    manifest["tables"]["provider_snapshots"] = [
        r for r in manifest["tables"]["provider_snapshots"] if r["sha256"] not in point_hashes
    ]
    content = {p: b for p, b in content.items() if p.stem not in point_hashes}
    # Prove asset destination is writable before committing database restoration.
    for path, body in content.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    with db.engine().begin() as conn:
        if any(conn.scalar(select(func.count()).select_from(t)) for t in db.metadata.sorted_tables):
            raise ValueError("Restore requires a fresh empty migrated database")
        for table in db.metadata.sorted_tables:
            for raw in manifest["tables"][table.name]:
                row = {
                    k: utc(v) if isinstance(table.c[k].type, DateTime) and v else v for k, v in raw.items()
                }
                conn.execute(table.insert().values(**row))
        removed = apply_tombstones(conn, latest_tombstones)
        # Restore serial sequence for the shared request ledger.
        from sqlalchemy import text

        conn.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('provider_budget','id'), COALESCE((SELECT max(id) FROM provider_budget),1), EXISTS(SELECT 1 FROM provider_budget))"
            )
        )
    return {
        "hashes_match": True,
        "created_at": manifest["created_at"],
        "deleted_rows_reapplied": removed,
        "external_sends_during_drill": 0,
    }


def write_backup() -> dict:
    destination = os.environ.get("BACKUP_DESTINATION", "")
    secret = os.environ.get("BACKUP_KEY", "")
    if not destination or not Path(destination).is_dir():
        raise RuntimeError("BLOCKED: no accessible existing BACKUP_DESTINATION directory configured")
    if not secret:
        raise RuntimeError("BLOCKED: BACKUP_KEY is not configured; refusing unencrypted backup")
    target = Path(destination)
    at = datetime.now(timezone.utc)
    payload = capture(secret.encode())
    name = "launch-visibility-" + at.strftime("%Y%m%dT%H%M%SZ") + ".fernet"
    fd, temp = tempfile.mkstemp(dir=target, prefix=".pending-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, target / name)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    # Keep seven daily snapshots and one per ISO week for the last four weeks.
    backups = sorted(target.glob("launch-visibility-*.fernet"), reverse=True)
    days, weeks = set(), set()
    for backup in backups:
        t = datetime.strptime(backup.stem.removeprefix("launch-visibility-"), "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        )
        day = t.date()
        week = t.isocalendar()[:2]
        keep = (len(days) < 7 and day not in days) or (len(weeks) < 4 and week not in weeks)
        if keep:
            days.add(day)
            weeks.add(week)
        else:
            backup.unlink()
    sync_deletion_ledger()
    return {"path": str(target / name), "sha256": hashlib.sha256(payload).hexdigest(), "at": stamp(at)}


def sync_deletion_ledger() -> None:
    target = Path(os.environ["BACKUP_DESTINATION"])
    secret = os.environ["BACKUP_KEY"]
    with db.engine().connect() as conn:
        tombstones = [
            {"id": r.id, "deleted_at": stamp(r.deleted_at)} for r in conn.execute(select(db.ledger))
        ]
    fd, temp = tempfile.mkstemp(dir=target, prefix=".ledger-pending-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(Fernet(secret.encode()).encrypt(json.dumps(tombstones).encode()))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, target / "deletion-ledger.fernet")
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["backup", "drill"])
    args = parser.parse_args()
    if args.command == "backup":
        print(json.dumps(write_backup()))
        return 0
    from implementation.operational_checks import backup_restore

    print(json.dumps(backup_restore(require_offhost=True), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
