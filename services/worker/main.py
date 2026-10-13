from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete, text
from sqlalchemy.dialects.postgresql import insert

from services.api import db
from packages.visibility.common import stamp
from .ingestion import cycle
from .notifications import plan, drain
from .jobs import schedule, claim, complete, retry


def purge(at: datetime) -> None:
    with db.engine().begin() as conn:
        point_docs = list(
            conn.execute(select(db.locations.c.body).where(db.locations.c.expires_at < at)).scalars()
        )
        old_locations = (
            conn.execute(select(db.locations.c.id).where(db.locations.c.expires_at < at)).scalars().all()
        )
        for id in old_locations:
            conn.execute(insert(db.ledger).values(id=id, deleted_at=at).on_conflict_do_nothing())
        conn.execute(delete(db.locations).where(db.locations.c.expires_at < at))
        old_owners = (
            conn.execute(select(db.sessions.c.id).where(db.sessions.c.expires_at < at)).scalars().all()
        )
        for id in old_owners:
            conn.execute(insert(db.ledger).values(id=id, deleted_at=at).on_conflict_do_nothing())
        conn.execute(delete(db.sessions).where(db.sessions.c.expires_at < at))
        from services.api.privacy import purge_points

        purge_points(conn, point_docs)
        conn.execute(delete(db.budget).where(db.budget.c.requested_at < at - timedelta(days=30)))
        conn.execute(delete(db.idempotency).where(db.idempotency.c.created_at < at - timedelta(days=1)))
        conn.execute(
            delete(db.jobs).where(
                db.jobs.c.state == "completed", db.jobs.c.created_at < at - timedelta(days=30)
            )
        )
        conn.execute(delete(db.cache).where(db.cache.c.key.like("admin-session:%"), db.cache.c.next_at < at))


def tick(at: datetime) -> None:
    # Session advisory lock is released on crash, leaving durable rows available for restart.
    with db.engine().connect() as leader:
        acquired = leader.scalar(text("SELECT pg_try_advisory_lock(77821411)"))
        if not acquired:
            return
        try:
            bucket = int(at.timestamp()) // 30
            for operation in ("ingest", "notices", "purge"):
                schedule(f"{operation}:{bucket}", {"operation": operation}, at)
            if os.environ.get("BACKUP_DESTINATION") and os.environ.get("BACKUP_KEY"):
                schedule("backup:" + str(at.date()), {"operation": "backup"}, at)
                schedule(f"deletion-ledger:{bucket}", {"operation": "deletion-ledger"}, at)
            for _ in range(10):
                job = claim(at)
                if not job:
                    break
                try:
                    operation = job["body"]["operation"]
                    if operation == "ingest":
                        cycle(at)
                    elif operation == "notices":
                        plan(at)
                        drain(at)
                    elif operation == "purge":
                        purge(at)
                    elif operation == "history":
                        from .history import refresh_page

                        refresh_page(job["body"]["snapshot"], job["body"]["offset"], at)
                    elif operation == "backup":
                        from ops.backup import write_backup

                        write_backup()
                    elif operation == "deletion-ledger":
                        from ops.backup import sync_deletion_ledger

                        sync_deletion_ledger()
                    else:
                        raise ValueError("Unsupported worker operation")
                    complete(job["id"])
                except Exception as exc:
                    logging.warning(
                        json.dumps(
                            {
                                "event": "job_failed",
                                "operation": job["body"].get("operation"),
                                "error_type": type(exc).__name__,
                            }
                        )
                    )
                    retry(job["id"], at)
            with db.engine().begin() as conn:
                conn.execute(
                    insert(db.cache)
                    .values(key="worker-heartbeat", body={"at": stamp(at)}, last_success_at=at, failures=0)
                    .on_conflict_do_update(
                        index_elements=["key"], set_={"body": {"at": stamp(at)}, "last_success_at": at}
                    )
                )
        finally:
            leader.execute(text("SELECT pg_advisory_unlock(77821411)"))


def main() -> None:
    from logging.handlers import TimedRotatingFileHandler
    from services.api.config import DATA

    folder = DATA / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(folder / "worker.jsonl", when="midnight", backupCount=30, utc=True)
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[handler, logging.StreamHandler()])
    # Library request logs include observer coordinates in NWS point URLs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    while True:
        try:
            tick(datetime.now(timezone.utc))
        except Exception as exc:
            logging.error(json.dumps({"event": "worker_cycle_failed", "error_type": type(exc).__name__}))
        time.sleep(30)


if __name__ == "__main__":
    main()
