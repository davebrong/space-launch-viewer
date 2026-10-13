from datetime import datetime, timedelta
from sqlalchemy import select
from packages.visibility.common import digest
from services.api import db
from services.worker.flight_plans import empty_plan


def read_flight_plan(conn, launch: dict, at: datetime) -> dict:
    cached = conn.execute(select(db.cache).where(db.cache.c.key == "flight-plan:launch:"+launch["id"])).mappings().first()
    fingerprint = digest([launch["name"], launch["pad_id"], launch["pad_point"]])
    if not cached or cached["body"].get("mission_fingerprint") != fingerprint:
        return empty_plan(launch, at, "pending", "Mission-specific flight-plan sources have not been checked yet.")
    result = dict(cached["body"])
    if cached["last_success_at"] < at-timedelta(hours=12) and result["state"] == "heading_only":
        result.update(state="stale", note="This published heading has not been refreshed recently; it is not a current trajectory.")
    return result
