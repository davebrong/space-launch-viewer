"""Worker-owned mission flight-plan discovery for every catalog mission.

Discovery has no vehicle-family, destination or launch-date-precision filter. Each
check records an explicit per-source state, so failures never stay "pending".
Robots policy, HTTP 403/429 and the shared request budgets are respected.

Sources:
- Next Spaceflight public mission pages: reported general departure heading.
- US Coast Guard NAVCEN SOLAR: published launch hazard areas (never a flight path).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from urllib.robotparser import RobotFileParser

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from packages.visibility.common import stamp, utc
from services.api import db
from services.api.adapters import navcen
from services.api.adapters.flight_plans import (
    INDEX_URL,
    ROBOTS_URL,
    SOURCE_NAME,
    mission_key,
    parse_heading,
    parse_index,
)
from services.api.flight_plans import KEY, combine, fingerprint
from .ingestion import fetch

NSF = "nextspaceflight"
SOLAR = "navcen-solar"
NAMES = {NSF: SOURCE_NAME, SOLAR: navcen.SOURCE_NAME}
PROVIDER = "flight-plan"
RETRY_S = {"found": 21600, "stale": 3600, "not_found": 21600, "ambiguous": 21600, "unavailable": 3600, "blocked": 86400, "queued": 300}


def user_agent() -> str:
    return os.environ.get("LV_USER_AGENT", "launch-visibility")


def cache_row(key: str):
    with db.engine().connect() as conn:
        return conn.execute(select(db.cache).where(db.cache.c.key == key)).mappings().first()


def failure_state(error: str | None) -> str:
    if error == "HTTP_403":
        return "blocked"
    if error == "BUDGET_DEFERRED":
        return "queued"
    if error == "HTTP_404":
        return "not_found"
    return "unavailable"


def robots_policy(url: str, key: str, provider: str, field: str, at: datetime, client=None) -> tuple[RobotFileParser | None, str | None]:
    """A 404 robots file means no crawl rules; other failures never authorize crawling."""
    body = fetch(url, key, provider, at, 86400, client=client)
    row = cache_row(key)
    error = row["error"] if row else "UNAVAILABLE"
    policy = RobotFileParser()
    if error == "HTTP_404":
        policy.parse([])
        return policy, None
    if body:
        # The last retrieved rules stay in force while a refresh is failing.
        policy.parse(body["payload"][field].splitlines())
        return policy, None
    return None, error


def near_launch(launch: dict, at: datetime) -> bool:
    return bool(
        launch["time_precision"] in ("exact", "window")
        and launch.get("net")
        and timedelta(0) <= utc(launch["net"]) - at <= timedelta(hours=6)
    )


def priority(launch: dict, at: datetime) -> tuple:
    """Imminent and dated missions first; unknown dates still enter discovery."""
    precise = launch["time_precision"] in ("exact", "window", "date") and launch.get("net")
    active = launch["status"] not in ("completed", "cancelled")
    when = utc(launch["net"]) if precise else at + timedelta(days=36500)
    return (not active, not precise, abs((when - at).total_seconds()), launch["id"])


def due(record: dict | None, launch: dict, at: datetime) -> bool:
    return (
        not record
        or record.get("mission_fingerprint") != fingerprint(launch)
        or "sources" not in record
        or not record.get("next_check_at")
        or utc(record["next_check_at"]) <= at
    )


def source_result(source: str, state: str, at: datetime, detail: str, **extra) -> dict:
    return {
        "name": NAMES[source],
        "state": state,
        "checked_at": stamp(at),
        "next_check_at": stamp(at + timedelta(seconds=RETRY_S[state])),
        "detail": detail,
        "evidence": [],
        **extra,
    }


def previous_sources(old: dict) -> dict:
    """Rebuild per-source results, including their evidence, from a stored record."""
    sources = {}
    for item in old.get("sources", []):
        source = item["source"]
        evidence = [e for e in old.get("evidence", []) if e.get("source_name") == item["name"]]
        sources[source] = {**{k: v for k, v in item.items() if k != "source"}, "evidence": evidence}
    return sources


def retain(result: dict, prior: dict | None) -> dict:
    """Keep the last validated evidence through transient access failures, labeled stale.

    A page that changed and failed validation, a removed page (404) or a new
    not-found result never reaches this branch, so its evidence is withdrawn.
    """
    if (
        prior
        and prior.get("evidence")
        and not result["evidence"]
        and result["state"] in ("queued", "unavailable", "blocked")
        and "parse_error" not in result
    ):
        return {
            **result,
            "state": "stale",
            "evidence": prior["evidence"],
            "source_url": prior.get("source_url") or prior["evidence"][0]["source_url"],
            "detail": result["detail"] + " Last retrieved information retained.",
        }
    return result


def save(launch: dict, at: datetime, results: dict, previous: dict | None) -> dict:
    old = (previous or {}) if (previous or {}).get("mission_fingerprint") == fingerprint(launch) else {}
    sources = previous_sources(old)
    for source, result in results.items():
        result = retain(result, sources.get(source))
        if near_launch(launch, at) and result["state"] in ("found", "stale"):
            result["next_check_at"] = stamp(at + timedelta(hours=1))
        sources[source] = result
    changes = list(old.get("changes", []))
    before = {e["source_url"]: e.get("departure_direction") for e in old.get("evidence", []) if e.get("departure_direction")}
    for result in results.values():
        for item in result["evidence"]:
            prior = before.get(item["source_url"])
            if prior and prior != item.get("departure_direction"):
                changes.append(
                    {"at": stamp(at), "source_url": item["source_url"], "from": prior, "to": item.get("departure_direction")}
                )
    record = combine(launch, at, sources, changes)
    with db.engine().begin() as conn:
        values = {"body": record, "next_at": utc(record["next_check_at"]), "last_success_at": at, "failures": 0, "error": None}
        conn.execute(
            insert(db.cache).values(key=KEY + launch["id"], **values).on_conflict_do_update(index_elements=["key"], set_=values)
        )
    return record


# Next Spaceflight ---------------------------------------------------------------


def known_url(previous: dict | None, launch: dict) -> str | None:
    if not previous or previous.get("mission_fingerprint") != fingerprint(launch):
        return None
    urls = {s.get("source_url") for s in previous.get("sources", []) if s.get("source") == NSF} - {None}
    return urls.pop() if len(urls) == 1 else None


def check_mission(
    launch: dict,
    entries: list[dict],
    index_meta: dict,
    policy: RobotFileParser,
    at: datetime,
    client=None,
    previous_url: str | None = None,
) -> dict:
    matches = [entry for entry in entries if entry["key"] == mission_key(launch["name"])]
    if not matches and previous_url:
        # Missions leave the upcoming index after launch; recheck the page matched earlier.
        # The page must still pass the same mission/pad validation.
        matches = [{"url": previous_url}]
    if not matches:
        return source_result(
            NSF,
            "not_found",
            at,
            f"Not listed in the checked Next Spaceflight index ({index_meta['entries']} entries). That index is partial.",
            **index_meta,
        )
    if len(matches) > 1:
        return source_result(NSF, "ambiguous", at, "Multiple source pages match this mission name; no direction assigned.", **index_meta)
    url = matches[0]["url"]
    if not policy.can_fetch(user_agent(), url):
        return source_result(NSF, "blocked", at, "Source crawling policy does not permit this mission page.", source_url=url, **index_meta)
    period = 3600 if near_launch(launch, at) else 21600
    page = fetch(url, "flight-plan:source:" + url, PROVIDER, at, period, client=client)
    row = cache_row("flight-plan:source:" + url)
    error = row["error"] if row else "UNAVAILABLE"
    if error == "HTTP_404":
        # A removed page withdraws its heading; an older cached copy is not reused.
        return source_result(NSF, "not_found", at, "The matched mission page no longer exists (HTTP 404).", source_url=url, **index_meta)
    if not page:
        return source_result(NSF, failure_state(error), at, f"Mission page could not be retrieved ({error}).", source_url=url, **index_meta)
    try:
        evidence = parse_heading(page["payload"]["html"], launch)
    except ValueError as exc:
        code = str(exc)
        state = "not_found" if code == "NO_PUBLISHED_HEADING" else "unavailable"
        detail = (
            "The matching mission page publishes no general trajectory."
            if state == "not_found"
            else f"The matching page failed validation ({code}); no direction assigned."
        )
        return source_result(NSF, state, at, detail, source_url=url, parse_error=code, **index_meta)
    evidence.update(source_url=url, source_sha256=page["provenance"]["sha256"], fetched_at=page["provenance"]["fetched_at"])
    stale = bool(error)
    return source_result(
        NSF,
        "stale" if stale else "found",
        at,
        "Last retrieved heading retained; the latest refresh failed." if stale else "Published general departure direction found.",
        source_url=url,
        **index_meta,
    ) | {"evidence": [evidence]}


def nextspaceflight(pending: list[dict], previous: dict, at: datetime, client=None) -> dict[str, dict]:
    def everyone(result: dict) -> dict[str, dict]:
        return {launch["id"]: dict(result) for launch in pending}

    policy, error = robots_policy(ROBOTS_URL, "flight-plan:robots", PROVIDER, "html", at, client)
    if policy is None:
        return everyone(source_result(NSF, failure_state(error), at, f"Source crawling policy could not be read ({error}); no pages were requested."))
    if not policy.can_fetch(user_agent(), INDEX_URL):
        return everyone(source_result(NSF, "blocked", at, "Source crawling policy does not permit the launch index."))
    index = fetch(INDEX_URL, "flight-plan:index", PROVIDER, at, 21600, client=client)
    row = cache_row("flight-plan:index")
    if not index:
        error = row["error"] if row else "UNAVAILABLE"
        return everyone(source_result(NSF, failure_state(error), at, f"The source launch index could not be retrieved ({error})."))
    try:
        entries = parse_index(index["payload"]["html"])
    except ValueError as exc:
        return everyone(source_result(NSF, "unavailable", at, f"The source launch index format is unsupported ({exc}).", parse_error=str(exc)))
    meta = {
        "index_url": INDEX_URL,
        "index_retrieved_at": index["provenance"]["fetched_at"],
        "index_sha256": index["provenance"]["sha256"],
        "entries": len(entries),
    }
    results = {}
    for position, launch in enumerate(pending):
        result = check_mission(launch, entries, meta, policy, at, client, known_url(previous.get(launch["id"]), launch))
        if result["state"] == "queued":
            # Budget exhausted: queue this and every remaining mission without requests.
            queued = source_result(NSF, "queued", at, "Waiting for the shared hourly source request budget.", **meta)
            results.update({later["id"]: dict(queued) for later in pending[position:]})
            break
        results[launch["id"]] = result
    return results


# NAVCEN SOLAR ---------------------------------------------------------------------


def solar(pending: list[dict], at: datetime, client=None) -> dict[str, dict]:
    def everyone(result: dict) -> dict[str, dict]:
        return {launch["id"]: dict(result) for launch in pending}

    policy, error = robots_policy(navcen.ROBOTS_URL, navcen.ROBOTS_URL, "robots", "robots_text", at, client)
    if policy is None:
        return everyone(source_result(SOLAR, failure_state(error), at, f"Source crawling policy could not be read ({error}); no data was requested."))
    if not policy.can_fetch(user_agent(), navcen.SOLAR_URL):
        return everyone(source_result(SOLAR, "blocked", at, "Source crawling policy does not permit the SOLAR data file."))
    data = fetch(navcen.SOLAR_URL, "flight-plan:navcen-solar", "navcen", at, 21600, client=client)
    row = cache_row("flight-plan:navcen-solar")
    error = row["error"] if row else "UNAVAILABLE"
    if not data:
        return everyone(source_result(SOLAR, failure_state(error), at, f"The SOLAR hazard data could not be retrieved ({error})."))
    meta = {"source_url": navcen.SOLAR_URL, "data_retrieved_at": data["provenance"]["fetched_at"], "notices": len(data["payload"]["notices"])}
    results = {}
    for launch in pending:
        state, notice, detail = navcen.associate(data["payload"]["notices"], launch)
        if not notice:
            results[launch["id"]] = source_result(SOLAR, state, at, detail, **meta)
            continue
        try:
            evidence = navcen.hazard_evidence(notice, launch)
        except ValueError as exc:
            results[launch["id"]] = source_result(SOLAR, "unavailable", at, f"Hazard notice unusable ({exc}).", parse_error=str(exc), **meta)
            continue
        evidence.update(
            source_url=navcen.SOLAR_URL,
            source_sha256=data["provenance"]["sha256"],
            fetched_at=data["provenance"]["fetched_at"],
        )
        stale = bool(error)
        results[launch["id"]] = source_result(
            SOLAR, "stale" if stale else "found", at, detail + (" The latest refresh failed." if stale else ""), **meta
        ) | {"evidence": [evidence]}
    return results


def refresh_flight_plans(at: datetime, client=None, launches: list[dict] | None = None) -> dict:
    if launches is None:
        with db.engine().connect() as conn:
            launches = list(conn.execute(select(db.launches.c.body)).scalars())
    with db.engine().connect() as conn:
        previous = {
            key[len(KEY) :]: body
            for key, body in conn.execute(
                select(db.cache.c.key, db.cache.c.body).where(db.cache.c.key.in_([KEY + launch["id"] for launch in launches]))
            ).all()
        }
    pending = sorted((x for x in launches if due(previous.get(x["id"]), x, at)), key=lambda x: priority(x, at))
    summary: dict = {"checked": 0, "deferred": 0, "states": {}}
    if not pending:
        return summary
    by_source = {NSF: nextspaceflight(pending, previous, at, client), SOLAR: solar(pending, at, client)}
    for launch in pending:
        results = {source: rows[launch["id"]] for source, rows in by_source.items() if launch["id"] in rows}
        saved = save(launch, at, results, previous.get(launch["id"]))
        summary["states"][saved["state"]] = summary["states"].get(saved["state"], 0) + 1
        summary["checked"] += 1
    summary["deferred"] = sum(r["state"] == "queued" for r in by_source[NSF].values())
    return summary
