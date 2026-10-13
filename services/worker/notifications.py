from __future__ import annotations

from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from packages.visibility.common import digest, utc, stamp
from services.api import db


def quiet(local_time: str, overnight_opt_in: bool) -> bool:
    value = time.fromisoformat(local_time)
    return not overnight_opt_in and (value >= time(22) or value < time(7))


def correction(
    shift_from_last_delivered_s: float, local_date_changed: bool, previously_notified: bool
) -> bool:
    return previously_notified and (abs(shift_from_last_delivered_s) >= 300 or local_date_changed)


def downgrade(persistent_s: float, inside_30m: bool, scrub: bool) -> bool:
    return persistent_s >= 600 or inside_30m or scrub


def delivery(now: datetime, expires_at: datetime, consent: bool) -> dict:
    if now >= expires_at:
        return {"deliver": False, "state": "expired"}
    if not consent:
        return {"deliver": False, "state": "cancelled"}
    return {"deliver": True, "state": "delivered"}


def viewing_bounds(assessment: dict, launch: dict) -> tuple | None:
    # Anchor to unrounded supported times, not display rounding or scheduled launch.
    supported = assessment.get("supported_intervals", [])
    if supported:
        return min(utc(w["start"]) for w in supported), max(utc(w["end"]) for w in supported)
    if not assessment["windows"] or not launch["net"]:
        return None
    t0 = utc(launch["actual_liftoff"] or launch["net"])
    start = min(t0 + timedelta(seconds=w["t_start_s"]) for w in assessment["windows"])
    end = max(t0 + timedelta(seconds=w["t_end_s"]) for w in assessment["windows"])
    return start, end


def milestone_preview(
    subscription: dict, assessment: dict, launch: dict, location: dict, at: datetime
) -> list[dict]:
    bounds = viewing_bounds(assessment, launch)
    if not bounds:
        return []
    start, end = bounds
    eligible = assessment["advice"] == "Worth a look" or (
        assessment["advice"] == "Possible" and subscription["allow_possible"]
    )
    eligible = eligible and assessment["fresh"] and assessment["display_status"] == "forecast"
    if launch["time_precision"] not in ("exact", "window"):
        return []
    rows = []
    for milestone, lead_s in (("planning_24h", 86400), ("viewing_30m", 1800)):
        if milestone not in subscription["milestones"] or (
            milestone == "viewing_30m" and launch["time_precision"] != "exact"
        ):
            continue
        due = start - timedelta(seconds=lead_s)
        local = due.astimezone(ZoneInfo(location["timezone"]))
        rows.append(
            {
                "notice_type": milestone,
                "due_at": stamp(due),
                "expires_at": stamp(end),
                "local": local.isoformat(),
                "zone": local.tzname(),
                "suppressed": quiet(local.time().isoformat(), subscription["overnight_opt_in"]),
                "eligible": bool(eligible and due > utc(subscription["created_at"]) and due > at),
                "reason": "eligible" if eligible else "advice_threshold_or_freshness",
            }
        )
    return rows


def enqueue(
    conn,
    subscription: dict,
    owner_id: str,
    launch: dict,
    assessment: dict,
    kind: str,
    due_at: datetime,
    expires_at: datetime,
    at: datetime,
) -> None:
    if expires_at <= due_at:
        return
    # Source retrieval timestamps alone do not change semantic notice revisions.
    material = digest(
        {
            "launch_revision": launch["revision"],
            "advice": assessment["advice"],
            "windows": assessment["windows"],
            "supported_intervals": assessment.get("supported_intervals", []),
            "subscription_revision": subscription["revision"],
            "type": kind,
        }
    )
    key = digest([subscription["id"], launch["attempt_id"], kind, material])
    doc = {
        "schema_version": "1.0",
        "id": str(uuid4()),
        "revision": 1,
        "subscription_id": subscription["id"],
        "launch_id": launch["id"],
        "attempt_id": launch["attempt_id"],
        "notice_type": kind,
        "material_revision": launch["revision"],
        "assessment_id": assessment["id"],
        "due_at": stamp(due_at),
        "expires_at": stamp(expires_at),
        "state": "pending",
        "channel": "in_app",
        "dedupe_key": key,
        "delivery_attempts": 0,
        "delivered_at": None,
        "provider_message_id": None,
        "reason_codes": assessment["reason_codes"],
        "content": f"{launch['name']}: {assessment['advice']}. "
        + ("Approximate flight profile. " if assessment["mode"] == "reconstructed" else "")
        + ("Conditional launch window. " if assessment["conditional"] else "")
        + "Refresh the assessment for current conditions.",
    }
    conn.execute(
        insert(db.outbox)
        .values(
            id=doc["id"],
            revision=1,
            body=doc,
            created_at=at,
            owner_id=owner_id,
            subscription_id=subscription["id"],
            launch_id=launch["id"],
            assessment_id=assessment["id"],
            dedupe_key=key,
            state="pending",
            due_at=due_at,
            expires_at=expires_at,
        )
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
    )


def deliver_one(outbox_id: str, at: datetime) -> bool:
    # Fixed lock order subscription -> launch -> outbox. Unique history row is transactional.
    with db.engine().begin() as conn:
        ref = conn.execute(select(db.outbox).where(db.outbox.c.id == outbox_id)).mappings().first()
        if not ref:
            return False
        sub = (
            conn.execute(
                select(db.subscriptions)
                .where(db.subscriptions.c.id == ref["subscription_id"])
                .with_for_update()
            )
            .mappings()
            .first()
        )
        launch = (
            conn.execute(select(db.launches).where(db.launches.c.id == ref["launch_id"]).with_for_update())
            .mappings()
            .first()
        )
        row = (
            conn.execute(select(db.outbox).where(db.outbox.c.id == outbox_id).with_for_update())
            .mappings()
            .first()
        )
        if not row or row["state"] not in ("pending", "retry", "claimed") or row["due_at"] > at:
            return False
        assessment = conn.scalar(
            select(db.assessments.c.body).where(db.assessments.c.id == row["assessment_id"])
        )
        valid = bool(
            sub
            and sub["enabled"]
            and launch
            and not launch["disabled"]
            and assessment
            and assessment["launch_revision"] == launch["revision"]
        )
        state = delivery(at, row["expires_at"], valid)["state"]
        if state == "delivered":
            loc = conn.scalar(select(db.locations.c.body).where(db.locations.c.id == sub["location_id"]))
            if not loc:
                state = "cancelled"
            else:
                from services.api.assessment import assess

                current = assess(conn, launch["body"], loc, sub["owner_id"], at)
                positive = row["body"]["notice_type"] in ("planning_24h", "viewing_30m")
                eligible = (
                    current["fresh"]
                    and current["display_status"] == "forecast"
                    and (
                        current["advice"] == "Worth a look"
                        or (current["advice"] == "Possible" and sub["body"]["allow_possible"])
                    )
                )
                if positive and not eligible:
                    state = "cancelled"
                elif quiet(
                    at.astimezone(ZoneInfo(loc["timezone"])).time().isoformat(),
                    sub["body"]["overnight_opt_in"],
                ):
                    state = "suppressed_quiet"
        body = {
            **row["body"],
            "state": state,
            "delivery_attempts": row["body"]["delivery_attempts"] + 1,
            "delivered_at": stamp(at) if state == "delivered" else None,
        }
        conn.execute(
            update(db.outbox)
            .where(db.outbox.c.id == row["id"])
            .values(state=state, body=body, lease_until=None)
        )
        if state in ("delivered", "suppressed_quiet", "expired"):
            conn.execute(
                insert(db.notices)
                .values(
                    id=row["id"],
                    outbox_id=row["id"],
                    owner_id=row["owner_id"],
                    revision=1,
                    body=body,
                    created_at=at,
                )
                .on_conflict_do_nothing(index_elements=["outbox_id"])
            )
        return state == "delivered"


def plan(at: datetime) -> None:
    from services.api.assessment import assess

    with db.engine().begin() as conn:
        subs = (
            conn.execute(
                select(db.subscriptions).where(db.subscriptions.c.enabled.is_(True)).with_for_update()
            )
            .mappings()
            .all()
        )
        launches = conn.execute(select(db.launches).where(db.launches.c.disabled.is_(False))).mappings().all()
        for subrow in subs:
            sub = subrow["body"]
            loc = conn.scalar(select(db.locations.c.body).where(db.locations.c.id == sub["location_id"]))
            if not loc:
                continue
            for launchrow in launches:
                launch = launchrow["body"]
                if not sub["all_supported_launches"] and launch["id"] not in sub["launch_ids"]:
                    continue
                result = assess(conn, launch, loc, subrow["owner_id"], at)
                for item in milestone_preview(sub, result, launch, loc, at):
                    if item["eligible"]:
                        enqueue(
                            conn,
                            sub,
                            subrow["owner_id"],
                            launch,
                            result,
                            item["notice_type"],
                            utc(item["due_at"]),
                            utc(item["expires_at"]),
                            at,
                        )
                previous = conn.execute(
                    select(db.notices.c.body)
                    .where(
                        db.notices.c.owner_id == subrow["owner_id"],
                        db.notices.c.body["subscription_id"].as_string() == sub["id"],
                        db.notices.c.body["launch_id"].as_string() == launch["id"],
                        db.notices.c.body["state"].as_string() == "delivered",
                    )
                    .order_by(db.notices.c.created_at.desc())
                    .limit(1)
                ).scalar()
                if not previous:
                    continue
                old = conn.scalar(
                    select(db.assessments.c.body).where(db.assessments.c.id == previous["assessment_id"])
                )
                if not old or old["id"] == result["id"]:
                    continue
                old_launch = conn.scalar(
                    select(db.revisions.c.body).where(
                        db.revisions.c.launch_id == launch["id"],
                        db.revisions.c.revision == old["launch_revision"],
                    )
                )
                if not old_launch:
                    continue
                bounds, old_bounds = viewing_bounds(result, launch), viewing_bounds(old, old_launch)
                shift = (bounds[0] - old_bounds[0]).total_seconds() if bounds and old_bounds else 0
                changed_date = bool(
                    bounds
                    and old_bounds
                    and bounds[0].astimezone(ZoneInfo(loc["timezone"])).date()
                    != old_bounds[0].astimezone(ZoneInfo(loc["timezone"])).date()
                )
                rank = {"Worth a look": 3, "Possible": 2, "Unlikely": 1, "Not enough data": 0}
                downgraded = rank[result["advice"]] < rank[old["advice"]]
                key = "downgrade:" + sub["id"] + ":" + launch["id"]
                state = conn.execute(select(db.cache).where(db.cache.c.key == key)).mappings().first()
                if downgraded and state is None:
                    conn.execute(db.cache.insert().values(key=key, body={"since": stamp(at)}, failures=0))
                if not downgraded and state:
                    from sqlalchemy import delete

                    conn.execute(delete(db.cache).where(db.cache.c.key == key))
                persistent = (at - utc(state["body"]["since"])).total_seconds() if state else 0
                inside = bool(old_bounds and at >= old_bounds[0] - timedelta(minutes=30))
                scrub = launch["status"] == "scrubbed"
                if (
                    scrub
                    or correction(shift, changed_date, True)
                    or (downgraded and downgrade(persistent, inside, scrub))
                ):
                    end = bounds[1] if bounds else old_bounds[1] if old_bounds else at + timedelta(hours=1)
                    if end > at:
                        enqueue(
                            conn,
                            sub,
                            subrow["owner_id"],
                            launch,
                            result,
                            "scrub" if scrub else "downgrade" if downgraded else "correction",
                            at,
                            end,
                            at,
                        )


def drain(at: datetime) -> int:
    with db.engine().connect() as conn:
        ids = (
            conn.execute(
                select(db.outbox.c.id)
                .where(db.outbox.c.state.in_(["pending", "retry", "claimed"]), db.outbox.c.due_at <= at)
                .order_by(db.outbox.c.due_at)
                .limit(100)
            )
            .scalars()
            .all()
        )
    return sum(deliver_one(id, at) for id in ids)
