"""Per-mission flight-plan evidence records shared by the API and worker.

A record keeps each checked source's state separately. Missing coverage (pending,
not found, unavailable, blocked) is never a negative visibility result, and a
departure heading or hazard area is never a timed, altitude-bearing path.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from packages.visibility.common import digest, stamp, utc
from services.api import db

KEY = "flight-plan:launch:"
CONFLICT_NOTE = " The reported departure heading points away from the published hazard areas, so no viewing estimate uses it."
STALE_AFTER = timedelta(hours=24)
# Ordered by precedence when combining source states into one mission state.
STATES = ("found", "stale", "ambiguous", "unavailable", "blocked", "queued", "pending", "not_found")
NOTES = {
    "found": "Mission-specific route information was found. See its evidence type and source.",
    "stale": "The last retrieved route information is retained, but the source could not be refreshed recently.",
    "ambiguous": "More than one source record matched this mission; no route information was assigned.",
    "unavailable": "A route source could not be checked. This does not establish that no flight plan exists.",
    "blocked": "Source access or crawling policy does not permit automatic checks. No bypass is attempted.",
    "queued": "Waiting for the shared source request budget.",
    "pending": "Mission-specific flight-plan sources have not been checked yet.",
    "not_found": "No matching mission was found in the checked sources. This does not establish that no flight plan exists.",
}


def fingerprint(launch: dict) -> str:
    return digest([launch["name"], launch["pad_id"], launch["pad_point"]])


def overlaps(a: dict, b: dict) -> bool:
    """Whether two clockwise compass sectors share any bearing."""

    def spans(s: dict) -> list[tuple[float, float]]:
        if s["end_deg"] - s["start_deg"] >= 360:
            return [(0.0, 360.0)]
        start, end = s["start_deg"] % 360, s["end_deg"] % 360
        return [(start, end)] if start <= end else [(start, 360.0), (0.0, end)]

    return any(x0 <= y1 and y0 <= x1 for x0, x1 in spans(a) for y0, y1 in spans(b))


def conflict(evidence: list[dict]) -> bool:
    """A reported heading that points away from every published hazard area is not used."""
    headings = [e["departure_sector_deg"] for e in evidence if e["evidence_type"] == "departure_heading"]
    hazards = [e["hazard_bearing_sector_deg"] for e in evidence if e["evidence_type"] == "hazard_corridor"]
    return bool(headings and hazards) and not any(overlaps(h, z) for h in headings for z in hazards)


def combine(launch: dict, at: datetime, sources: dict, changes: list | None = None) -> dict:
    """Build one mission record from independent per-source results."""
    evidence = [e for s in sources.values() for e in s.get("evidence", [])]
    states = {s["state"] for s in sources.values()} or {"pending"}
    state = next(s for s in STATES if s in states)
    if evidence and state not in ("found", "stale"):
        state = "stale" if "stale" in states else "found"
    next_checks = [s["next_check_at"] for s in sources.values() if s.get("next_check_at")]
    return {
        "schema_version": "1.0",
        "launch_id": launch["id"],
        "state": state,
        "checked_at": stamp(at),
        "next_check_at": min(next_checks) if next_checks else None,
        "mission_fingerprint": fingerprint(launch),
        "evidence": evidence,
        "sources": [{"source": k, **{f: v for f, v in s.items() if f != "evidence"}} for k, s in sorted(sources.items())],
        "changes": (changes or [])[-10:],
        "trajectory_available": any(e["evidence_type"] == "published_path" for e in evidence),
        "conflict": conflict(evidence),
        "note": NOTES[state] + (CONFLICT_NOTE if conflict(evidence) else ""),
    }


def empty_record(launch: dict, at: datetime, state: str = "pending") -> dict:
    return combine(launch, at, {}) | {"state": state, "note": NOTES[state], "checked_at": None}


def identity(record: dict | None) -> str | None:
    """Calculation-relevant content only, so check timestamps do not defeat caching."""
    return digest({"state": record["state"], "evidence": record["evidence"], "conflict": record.get("conflict")}) if record else None


def current(record: dict | None, launch: dict, at: datetime) -> dict:
    """Validate a cached record against the current mission identity and age."""
    if not record or record.get("mission_fingerprint") != fingerprint(launch) or "evidence" not in record:
        return empty_record(launch, at)
    result = dict(record)
    if result["state"] == "found" and result["checked_at"] and utc(result["checked_at"]) < at - STALE_AFTER:
        result.update(state="stale", note=NOTES["stale"])
    return result


def read_flight_plan(conn, launch: dict, at: datetime) -> dict:
    body = conn.scalar(select(db.cache.c.body).where(db.cache.c.key == KEY + launch["id"]))
    return current(body, launch, at)


def read_many(conn, launches: list[dict], at: datetime) -> dict[str, dict]:
    if not launches:
        return {}
    rows = conn.execute(
        select(db.cache.c.key, db.cache.c.body).where(db.cache.c.key.in_([KEY + launch["id"] for launch in launches]))
    ).all()
    bodies = {key[len(KEY) :]: body for key, body in rows}
    return {launch["id"]: current(bodies.get(launch["id"]), launch, at) for launch in launches}


def family(launch: dict) -> str:
    variant = (launch.get("vehicle_variant") or "").strip()
    if not variant or variant.lower().startswith("unknown"):
        return "Unknown vehicle"
    words = variant.split()
    # Multi-word family names ("Falcon 9", "New Glenn", "Space Launch System"); variants dropped.
    size = {"Falcon": 2, "New": 2, "Atlas": 2, "Terran": 2, "Long": 2, "Space": 3}.get(words[0], 1)
    return " ".join(words[:size])


def coverage(launches: list[dict], records: dict[str, dict]) -> dict:
    """Honest denominators: every catalog mission, regardless of date precision or vehicle."""
    by_state = {s: 0 for s in STATES}
    by_evidence: dict[str, int] = {}
    by_family: dict[str, dict] = {}
    by_precision: dict[str, dict] = {}
    for launch in launches:
        record = records[launch["id"]]
        by_state[record["state"]] += 1
        kinds = sorted({e["evidence_type"] for e in record["evidence"]})
        for kind in kinds:
            by_evidence[kind] = by_evidence.get(kind, 0) + 1
        for table, name in ((by_family, family(launch)), (by_precision, launch["time_precision"])):
            row = table.setdefault(name, {"missions": 0, "with_route_information": 0})
            row["missions"] += 1
            row["with_route_information"] += bool(kinds)
    return {
        "missions": len(launches),
        "with_route_information": sum(bool(r["evidence"]) for r in records.values()),
        "with_timed_path": sum(r["trajectory_available"] for r in records.values()),
        "by_state": by_state,
        "by_evidence_type": by_evidence,
        "by_vehicle_family": dict(sorted(by_family.items())),
        "by_time_precision": dict(sorted(by_precision.items())),
        "note": "Route information means a mission-specific published heading, hazard area or path. Headings and hazard areas are not timed trajectories; missing coverage is not a negative visibility result.",
    }
