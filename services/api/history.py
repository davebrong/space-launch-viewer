"""Public historical schedule pages. Provider retrieval remains worker-owned."""

from datetime import datetime
import re
from urllib.parse import urlencode

from sqlalchemy import select

from . import db
from packages.visibility.common import stamp

HEAD_KEY = "ll2:history:head"
HEAD_URL = "https://ll.thespacedevs.com/2.3.0/launches/previous/?limit=100&location__ids=12,27&ordering=-net"


def historical_launch(conn, launch_id: str) -> tuple[dict, dict] | None:
    """Resolve a browsed archive record without adding it to the upcoming catalog."""
    from .adapters.ll2 import normalize

    cached = (
        conn.execute(
            select(db.cache)
            .where(
                db.cache.c.key.like("ll2:history:%"),
                db.cache.c.last_success_at.is_not(None),
                db.cache.c.body["payload"]["results"].contains([{"id": launch_id}]),
            )
            .order_by(db.cache.c.last_success_at.desc(), db.cache.c.key)
            .limit(1)
        )
        .mappings()
        .first()
    )
    if not cached:
        return None
    body = cached["body"]
    raw = next(row for row in body["payload"]["results"] if row["id"] == launch_id)
    launch = normalize(raw, body["provenance"])
    # Legacy archive records lack precision metadata. Preserve the recorded day
    # for untimed nearby potential; never promote their clock to a known time.
    if raw.get("net_precision") is None and launch["net"]:
        launch.update(time_precision="date", date_label=launch["net"][:10], date_basis_timezone="UTC")
    return launch, raw


def page_key(snapshot: str, offset: int) -> str:
    return HEAD_KEY if offset == 0 else f"ll2:history:{snapshot}:{offset}"


def page_url(head: dict, offset: int) -> str:
    # Freeze the upper launch date so a new launch cannot shift older pages.
    return HEAD_URL + "&" + urlencode({"net__lte": head["payload"]["results"][0]["net"], "offset": offset})


def read_page(cursor: str | None, at: datetime) -> dict:
    from services.worker.jobs import schedule

    offset, snapshot = 0, ""
    if cursor:
        if not re.fullmatch(r"[0-9a-f]{64}:[1-9][0-9]*", cursor):
            raise ValueError("Invalid history cursor")
        snapshot, value = cursor.split(":")
        offset = int(value)
        if offset % 100:
            raise ValueError("Invalid history cursor")
    with db.engine().connect() as conn:
        head = conn.execute(select(db.cache).where(db.cache.c.key == HEAD_KEY)).mappings().first()
        head_body = head["body"] if head and head["last_success_at"] else None
        if cursor and (not head_body or snapshot != head_body["provenance"]["sha256"]):
            raise ValueError("History refreshed. Reload past launches to continue.")
        if cursor and offset >= head_body["payload"]["count"]:
            raise ValueError("History cursor is outside the archive")
        if head_body:
            snapshot = head_body["provenance"]["sha256"]
        key = page_key(snapshot, offset)
        cached = conn.execute(select(db.cache).where(db.cache.c.key == key)).mappings().first()
    due = not cached or not cached["next_at"] or cached["next_at"] <= at
    if due:
        schedule(
            f"history:{snapshot}:{offset}:{int(at.timestamp()) // 30}",
            {"operation": "history", "snapshot": snapshot, "offset": offset},
            at,
        )
    body = cached["body"] if cached and cached["last_success_at"] else None
    error = cached["error"] if cached else None
    rows = []
    if body:
        for row in body["payload"]["results"]:
            precision = (row.get("net_precision") or {}).get("id")
            rows.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "net": row.get("net"),
                    "date_only": precision == 5,
                    "time_known": precision in (0, 1, 2, 3, 4),
                    "pad_name": row["pad"]["name"],
                    "status": row["status"]["name"],
                    "updated_at": row.get("last_updated"),
                    "source_url": "https://ll.thespacedevs.com/2.3.0/launches/" + row["id"] + "/",
                }
            )
    count = head_body["payload"]["count"] if head_body else None
    return {
        "rows": rows,
        "provider_count": count,
        "next_cursor": f"{snapshot}:{offset + 100}" if body and body["payload"].get("next") else None,
        "fetched_at": body["provenance"]["fetched_at"] if body else None,
        "source_url": body["provenance"]["source_url"] if body else HEAD_URL,
        "state": "ready" if body else "unavailable" if error else "pending",
        "error": error,
        "refreshing": due,
        "retry_at": stamp(cached["next_at"]) if error and cached and cached["next_at"] else None,
    }
