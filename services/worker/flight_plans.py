"""Worker-owned mission plan discovery, independent of date precision and vehicle family."""
from datetime import datetime, timedelta
from urllib.robotparser import RobotFileParser
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from services.api import db
from services.api.adapters.flight_plans import INDEX_URL, VERSION, mission_key, parse_index, parse_heading
from packages.visibility.common import stamp, digest
from .ingestion import fetch


def empty_plan(launch: dict, at: datetime, state: str, note: str) -> dict:
    return {"launch_id": launch["id"], "state": state, "source_name": None, "source_url": None,
            "source_sha256": None, "fetched_at": None, "checked_at": stamp(at),
            "evidence_type": None, "departure_direction": None, "trajectory_available": False,
            "parser_version": VERSION, "note": note,
            "mission_fingerprint": digest([launch["name"], launch["pad_id"], launch["pad_point"]])}


def refresh_flight_plans(at: datetime, client=None, launches: list[dict] | None = None) -> None:
    if launches is None:
        with db.engine().connect() as conn:
            launches = list(conn.execute(select(db.launches.c.body)).scalars())
    # Robots retrieval is also cached and budgeted. A 404 means no robots rules;
    # denial/transport failures never authorize crawling.
    robots = fetch("https://nextspaceflight.com/robots.txt", "flight-plan:robots", "flight-plan", at, 86400, client=client)
    with db.engine().connect() as conn:
        robot_cache = conn.execute(select(db.cache).where(db.cache.c.key == "flight-plan:robots")).mappings().first()
    robot_error = robot_cache["error"] if robot_cache else "unavailable"
    allowed = robot_error == "HTTP_404"
    if robots and not robot_error:
        parser = RobotFileParser()
        parser.parse(robots["payload"]["html"].splitlines())
        allowed = parser.can_fetch("launch-visibility", INDEX_URL)
    if not allowed:
        return
    index = fetch(INDEX_URL, "flight-plan:index", "flight-plan", at, 21600, client=client)
    with db.engine().connect() as conn:
        index_error = conn.scalar(select(db.cache.c.error).where(db.cache.c.key == "flight-plan:index"))
    if not index or index_error:
        return
    try:
        entries = parse_index(index["payload"]["html"])
    except ValueError:
        return
    for launch in launches:
        key = "flight-plan:launch:" + launch["id"]
        with db.engine().connect() as conn:
            cached = conn.execute(select(db.cache).where(db.cache.c.key == key)).mappings().first()
        fingerprint = digest([launch["name"], launch["pad_id"], launch["pad_point"]])
        if cached and cached["next_at"] > at and cached["body"].get("mission_fingerprint") == fingerprint:
            continue
        matches = [entry for entry in entries if entry["key"] == mission_key(launch["name"])]
        plan = empty_plan(launch, at, "not_found", "No matching mission in the checked source index. This does not establish that no flight plan exists.")
        if len(matches) > 1:
            plan.update(state="ambiguous", note="Multiple source records match; no direction assigned.")
        elif matches:
            url = matches[0]["url"]
            if robots and not parser.can_fetch("launch-visibility", url):
                plan.update(state="unavailable", note="Source crawling policy does not permit this mission page.")
            else:
                result = fetch(url, "flight-plan:source:" + url, "flight-plan", at, 21600, client=client)
                with db.engine().connect() as conn:
                    source_cache = conn.execute(select(db.cache).where(db.cache.c.key == "flight-plan:source:" + url)).mappings().first()
                if result:
                    try:
                        plan.update(parse_heading(result["payload"]["html"], launch))
                        plan.update(source_url=url, source_sha256=result["provenance"]["sha256"], fetched_at=result["provenance"]["fetched_at"])
                        if source_cache["error"]:
                            plan.update(state="stale", note="Last retrieved heading retained; source refresh failed. Not a current flight plan.")
                    except ValueError as exc:
                        plan.update(state="unavailable", source_url=url, note=str(exc))
                else:
                    plan.update(state="unavailable", source_url=url, note=source_cache["error"] if source_cache else "Source unavailable")
        with db.engine().begin() as conn:
            conn.execute(insert(db.cache).values(key=key, body=plan, next_at=at+timedelta(hours=6), last_success_at=at, failures=0)
                         .on_conflict_do_update(index_elements=["key"],set_={"body":plan,"next_at":at+timedelta(hours=6),"last_success_at":at}))
