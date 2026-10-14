from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from packages.visibility import RULESET
from packages.visibility.common import digest, stamp, utc
from packages.visibility.astronomy import model_manifest, solar_events
from packages.visibility.ensemble import reconstruct, evaluate_candidate, envelope
from packages.visibility.rules import Inputs, decide
from packages.visibility.time import presentation
from packages.visibility.weather import select as weather_select, fresh as weather_fresh
from packages.visibility.planning import calculate_plan, MODEL_SHA256
from .adapters.routes import admit_route, compatible
from .adapters.nws import normalize as nws_normalize
from .flight_plans import identity, read_flight_plan
from . import db


def current_versions(rows: list[dict], fields: tuple[str, ...]) -> list[dict]:
    """Equal-revision candidates coexist; a later reviewed revision supersedes them."""
    latest = {}

    def identity(row):
        return tuple(
            str(row["provenance"][0]["source_url"] if field == "source_url" else row.get(field))
            for field in fields
        )

    for row in rows:
        key = identity(row)
        latest[key] = max(latest.get(key, 0), row["revision"])
    return [r for r in rows if r["revision"] == latest[identity(r)]]


def cached_weather(conn, location: dict) -> list[dict]:
    p = location["point"]
    coord = f"{p['latitude_deg']:.4f},{p['longitude_deg']:.4f}"
    info = conn.scalar(select(db.cache.c.body).where(db.cache.c.key == "point:" + coord))
    if not info or "payload" not in info:
        return []
    url = info["payload"]["properties"].get("forecastGridData")
    cached = conn.execute(select(db.cache).where(db.cache.c.key == url)).mappings().first()
    data = cached["body"] if cached else None
    if not data or "payload" not in data:
        return []
    try:
        rows = nws_normalize(data["payload"], data["provenance"], url)
        if cached["error"]:
            for row in rows:
                row["missing_flags"].append("provider_refresh_failed")
        return rows
    except ValueError:
        return []


def schedule_fresh(launch: dict, now: datetime) -> bool:
    if not launch["provenance"]:
        return False
    age = (now - utc(launch["provenance"][0]["fetched_at"])).total_seconds()
    near = launch["net"] and (utc(launch["net"]) - now).total_seconds() <= 21600
    source = launch.get("source_updated_at")
    return -300 <= age <= (900 if near else 3600) and (
        not source or (utc(source) - now).total_seconds() <= 300
    )


def calculate(
    launch: dict,
    location: dict,
    route_rows: list[dict],
    profile_rows: list[dict],
    weather_rows: list[dict],
    now: datetime,
    evaluate_windows: bool = True,
    source_available: bool = True,
    flight_plan: dict | None = None,
) -> dict:
    if not location["confirmed"] or not location["timezone"]:
        raise ValueError("UNCONFIRMED_LOCATION")
    model = model_manifest()
    status = presentation(
        launch["time_precision"],
        now,
        launch["net"],
        launch["actual_liftoff"],
        "disabled" if launch["disabled"] else launch["status"],
        schedule_fresh(launch, now),
    )["display_status"]
    at = utc(launch["actual_liftoff"] or launch["net"]) if launch["net"] else now
    provenance = launch["provenance"] + location["provenance"]
    matching, reasons = [], []
    for route in route_rows:
        ok, why = admit_route(route, launch, at, now)
        if ok:
            matching.append(route)
        else:
            reasons.extend(why)
    approved_profiles = [p for p in profile_rows if compatible(p, launch)[0]]
    mode, member, candidates, intervals = "unavailable", False, [], []
    for route in matching:
        provenance.extend(route["provenance"])
        if route["evidence_type"] == "official_guidance":
            g = route["guidance"]
            if (
                g
                and g["location_id"] == location["id"]
                and g["membership"] == "included"
                and g["membership_method"] != "unclassified"
            ):
                mode, member = "official_guidance", True
                if (
                    g["timing_basis"] == "liftoff_relative"
                    and g["relative_start_s"] is not None
                    and g["relative_end_s"] is not None
                ):
                    intervals.append(
                        {
                            "start": stamp(at + timedelta(seconds=g["relative_start_s"])),
                            "end": stamp(at + timedelta(seconds=g["relative_end_s"])),
                        }
                    )
                elif g["viewing_interval"]:
                    intervals.append(g["viewing_interval"])
        elif route["evidence_type"] == "published_path" and mode != "official_guidance":
            for profile in approved_profiles:
                try:
                    samples = reconstruct(profile, route)
                    candidate = evaluate_candidate(samples, location["point"], at)
                    first_burns = {}
                    for burn in sorted(profile["powered_intervals"], key=lambda b: b["start_s"]):
                        first_burns.setdefault(burn["stage"], burn)
                    candidate["complete"] = all(
                        (rows := [s for s in samples if s["stage"] == stage])
                        and rows[0]["t_s"] == burn["start_s"]
                        and rows[-1]["t_s"] == burn["end_s"]
                        and all(
                            b["t_s"] - a["t_s"] <= 15 and a["segment_id"] == b["segment_id"]
                            for a, b in zip(rows, rows[1:])
                        )
                        for stage, burn in first_burns.items()
                    )
                    candidate["id"] = route["id"] + ":" + profile["id"]
                    candidates.append(candidate)
                    provenance.extend(profile["provenance"])
                except ValueError as exc:
                    reasons.append(str(exc))
            if candidates:
                mode = "reconstructed"
        elif route["evidence_type"] == "hazard_corridor" and mode == "unavailable":
            mode = "route_screening"
    windows = envelope(candidates, at) if mode == "reconstructed" else []
    if mode == "reconstructed":
        intervals = [
            {
                "start": stamp(at + timedelta(seconds=w["t_start_s"])),
                "end": stamp(at + timedelta(seconds=w["t_end_s"])),
            }
            for w in windows
        ]
    weather_state = "unavailable"
    usable_seconds = 0.0
    weather_is_fresh = False
    selected = []
    weather_checks = []
    complete_negative = bool(candidates) and all(c["complete"] and c["all_below_horizon"] for c in candidates)
    weather_intervals = intervals
    if complete_negative and not intervals:
        weather_intervals = [
            {
                "start": stamp(at + timedelta(seconds=min(s["t_s"] for s in c["samples"]))),
                "end": stamp(at + timedelta(seconds=max(s["t_s"] for s in c["samples"]))),
            }
            for c in candidates
        ]
    if weather_rows and weather_intervals:
        for interval in weather_intervals:
            choice = weather_select(interval, weather_rows)
            covered_rows = [
                r
                for r in weather_rows
                if utc(r["start"]) < utc(interval["end"]) and utc(r["end"]) > utc(interval["start"])
            ]
            relevant = [interval] if complete_negative else choice["usable"] or [interval]
            fresh_rows = [
                r
                for r in covered_rows
                if any(utc(r["start"]) < utc(v["end"]) and utc(r["end"]) > utc(v["start"]) for v in relevant)
            ]
            is_fresh = bool(fresh_rows) and all(
                "provider_refresh_failed" not in r.get("missing_flags", [])
                and weather_fresh(
                    (now - utc(r["provenance"][0]["fetched_at"])).total_seconds(),
                    (now - utc(r["provenance"][0]["issued_at"])).total_seconds()
                    if r["provenance"][0]["issued_at"]
                    else None,
                    choice["tier"] != "unavailable",
                )
                for r in fresh_rows
            )
            if complete_negative and any(p["tier"] in ("unavailable", "stale") for p in choice["parts"]):
                is_fresh = False
            weather_checks.append(is_fresh)
            if is_fresh:
                weather_is_fresh = True
                if weather_state not in ("clear", "mixed") or choice["tier"] == "clear":
                    weather_state = choice["tier"]
                if intervals:
                    selected.extend(choice["usable"])
                usable_seconds = max(
                    usable_seconds,
                    max(
                        ((utc(r["end"]) - utc(r["start"])).total_seconds() for r in choice["usable"]),
                        default=0,
                    ),
                )
            else:
                reasons.append("weather_stale_or_incomplete")
            provenance.extend(r["provenance"][0] for r in covered_rows)
    if complete_negative:
        weather_is_fresh = bool(weather_checks) and all(weather_checks)
    if not intervals and candidates and all(c["all_below_horizon"] for c in candidates):
        # Combined negative still needs covered/fresh weather per D09.
        reasons.append("below_horizon_geometry_only")
    complete = (bool(intervals) or complete_negative) and launch["time_precision"] in ("exact", "window")
    if mode == "reconstructed" and weather_state == "poor":
        complete = complete and all(c["complete"] for c in candidates)
    decision = decide(
        Inputs(
            "scheduled" if status == "forecast" else status,
            mode,
            "approved" if matching else "missing",
            "compatible" if approved_profiles else "missing",
            complete,
            schedule_fresh(launch, now) and source_available and weather_is_fresh,
            weather_state,
            usable_seconds if intervals or complete_negative else None,
            bool(candidates) and all(c["all_below_horizon"] for c in candidates),
            member,
        )
    )
    if not matching:
        reasons.append("mission_route_unavailable")
    if not source_available:
        reasons.append("schedule_refresh_failed")
    if not approved_profiles and mode != "official_guidance":
        reasons.append("compatible_profile_unavailable")
    if not weather_rows:
        reasons.append("observer_weather_unavailable")
    dates = {at.astimezone(ZoneInfo(location["timezone"])).date()}
    if launch["time_precision"] == "window" and launch["window"]:
        first = utc(launch["window"]["start"]).astimezone(ZoneInfo(location["timezone"])).date()
        last = utc(launch["window"]["end"]).astimezone(ZoneInfo(location["timezone"])).date()
        if (last - first).days <= 3:
            dates.update(first + timedelta(days=d) for d in range((last - first).days + 1))
    for interval in intervals:
        day = utc(interval["start"]).astimezone(ZoneInfo(location["timezone"])).date()
        end = (
            (utc(interval["end"]) - timedelta(microseconds=1))
            .astimezone(ZoneInfo(location["timezone"]))
            .date()
        )
        while day <= end:
            dates.add(day)
            day += timedelta(days=1)
    events = []
    for day in sorted(dates):
        try:
            p = location["point"]
            events.append(
                solar_events(
                    str(day), location["timezone"], p["latitude_deg"], p["longitude_deg"], p["altitude_m"]
                )
            )
        except (ValueError, OverflowError):
            reasons.append("astronomy_date_unsupported")
    provenance = list({digest(p): p for p in provenance}.values())
    input_hashes = sorted(
        {p["sha256"] for p in provenance}
        | {
            digest(location),
            digest(launch),
            digest(route_rows),
            digest(profile_rows),
            digest(weather_rows),
            model["sha256"],
        }
    )
    planning = (
        calculate_plan(launch, location, weather_rows, now, flight_plan)
        if mode in ("unavailable", "route_screening")
        else None
    )
    key = digest(
        {
            "inputs": input_hashes,
            "rules": RULESET,
            "planning_model": MODEL_SHA256,
            "planning_scenario": planning,
            "flight_plan": identity(flight_plan),
            "advice": decision,
            "status": status,
            "fresh": schedule_fresh(launch, now) and source_available and weather_is_fresh,
        }
    )
    result = {
        "schema_version": "1.0",
        "id": key,
        "revision": 1,
        "launch_id": launch["id"],
        "launch_revision": launch["revision"],
        "attempt_id": launch["attempt_id"],
        "location_id": location["id"],
        "location_revision": location["revision"],
        "computed_at": stamp(now),
        "as_of": stamp(now),
        "ruleset": RULESET,
        "astronomy_version": model["version"],
        "ephemeris_sha256": model["sha256"],
        "input_hashes": input_hashes,
        "evidence_ids": [r["id"] for r in matching],
        "profile_ids": [p["id"] for p in approved_profiles] if candidates else [],
        "mode": mode,
        "advice": decision["advice"],
        "display_status": status,
        "weather_state": weather_state,
        "fresh": schedule_fresh(launch, now) and source_available and weather_is_fresh,
        "conditional": launch["time_precision"] == "window",
        "all_tracks_agree": len({digest(c["windows"]) for c in candidates}) == 1 if candidates else None,
        "lighting_flag": any(c["lighting_flag"] for c in candidates),
        "windows": windows,
        "planning_scenario": planning,
        "solar_events": events,
        "official_intervals": intervals if mode == "official_guidance" else [],
        "supported_intervals": [{"start": r["start"], "end": r["end"]} for r in selected],
        "alternatives": [],
        "missing_flags": sorted(set(reasons)),
        "reason_codes": decision["reason_codes"],
        "limitations": [
            "Unobstructed geometric horizon; buildings and terrain are not modeled.",
            "No measured detection probability.",
        ]
        + (
            [
                "Historical flight profiles are approximate; candidate spread is not a statistical confidence interval.",
                "Clouds along a low-elevation sightline may differ from the observer grid.",
            ]
            if candidates
            else []
        )
        + (["Altitude and timed visibility unresolved."] if mode == "route_screening" else []),
        "provenance": provenance,
    }
    if (
        evaluate_windows
        and launch["time_precision"] == "window"
        and launch["window"]
        and (candidates or member)
    ):
        from packages.visibility.time import alternatives

        start, end = utc(launch["window"]["start"]), utc(launch["window"]["end"])
        offsets = {w[k] for w in windows for k in ("t_start_s", "t_end_s")} or {0}
        boundaries = [
            utc(row[k]) - timedelta(seconds=offset)
            for row in weather_rows
            for k in ("start", "end")
            for offset in offsets
        ]
        boundaries += [
            utc(t["at"]) - timedelta(seconds=offset)
            for event in events
            for t in event["transitions"]
            for offset in offsets
        ]

        alternative_intervals = []

        def evaluate(t):
            alternative = calculate(
                {**launch, "net": stamp(t), "time_precision": "exact"},
                location,
                route_rows,
                profile_rows,
                weather_rows,
                now,
                False,
                source_available,
                flight_plan,
            )
            alternative_intervals.extend(alternative["supported_intervals"])
            return {
                "advice": alternative["advice"],
                "reason_codes": alternative["reason_codes"],
                "weather_state": alternative["weather_state"],
            }

        try:
            result["alternatives"] = alternatives(start, end, evaluate, boundaries)
            merged = []
            for interval in sorted(alternative_intervals, key=lambda i: i["start"]):
                if merged and utc(interval["start"]) <= utc(merged[-1]["end"]):
                    merged[-1]["end"] = max(merged[-1]["end"], interval["end"])
                else:
                    merged.append(dict(interval))
            result["supported_intervals"] = merged
            if len({digest(r["result"]) for r in result["alternatives"]}) > 1:
                result["reason_codes"].append("conditional_alternatives_disagree")
                result["advice"] = "Not enough data"
        except ValueError:
            result["advice"] = "Not enough data"
            result["reason_codes"].append("time_insufficient")
        result["id"] = digest({"base": key, "alternatives": result["alternatives"]})
    return result


def assess(conn, launch: dict, location: dict, owner_id: str, now: datetime) -> dict:
    route_rows = (
        conn.execute(
            select(db.routes.c.body).where(db.routes.c.body["launch_id"].as_string() == launch["id"])
        )
        .scalars()
        .all()
    )
    profiles = conn.execute(select(db.profiles.c.body)).scalars().all()
    profiles = current_versions(
        profiles, ("historical_mission", "vehicle_variant", "mission_class", "recovery_configuration")
    )
    route_rows = current_versions(
        route_rows, ("launch_id", "attempt_id", "evidence_type", "source_format", "source_url")
    )
    checked_routes = []
    for route in route_rows:
        receipt = (
            conn.execute(select(db.cache).where(db.cache.c.key == "route-check:" + route["id"]))
            .mappings()
            .first()
        )
        if receipt:
            route = dict(route)
            body = receipt["body"]
            if (
                receipt["error"]
                or body.get("payload", {}).get("source_sha256") != route["provenance"][0]["sha256"]
            ):
                route["admission"] = "unsupported"
            elif body.get("provenance"):
                route["provenance"] = [
                    {**route["provenance"][0], "fetched_at": body["provenance"]["fetched_at"]},
                    *route["provenance"][1:],
                ]
        checked_routes.append(route)
    route_rows = checked_routes
    weather_rows = cached_weather(conn, location)
    flight_plan = read_flight_plan(conn, launch, now)
    source_available = not conn.scalar(select(db.cache.c.error).where(db.cache.c.key == "ll2"))
    # Runtime freshness and schedule status enter cache lookup; immutable archives are never overwritten.
    freshness = {
        "schedule": schedule_fresh(launch, now),
        "past_net": bool(launch["net"] and now >= utc(launch["net"])),
        "source_available": source_available,
    }
    at = utc(launch["actual_liftoff"] or launch["net"]) if launch["net"] else now
    freshness["routes"] = [admit_route(route, launch, at, now) for route in route_rows]
    for row in weather_rows:
        p = row["provenance"][0]
        freshness[p["sha256"]] = weather_fresh(
            (now - utc(p["fetched_at"])).total_seconds(),
            (now - utc(p["issued_at"])).total_seconds() if p["issued_at"] else None,
            True,
        )
    lookup = (
        "assessment:"
        + owner_id
        + ":"
        + digest([launch, location, route_rows, profiles, weather_rows, freshness, MODEL_SHA256, identity(flight_plan)])
    )
    cached = conn.execute(select(db.cache).where(db.cache.c.key == lookup)).mappings().first()
    if cached and cached["next_at"] and cached["next_at"] > now:
        result = conn.scalar(
            select(db.assessments.c.body).where(db.assessments.c.id == cached["body"]["assessment_id"])
        )
        if result:
            return result
    result = calculate(
        launch,
        location,
        route_rows,
        profiles,
        weather_rows,
        now,
        source_available=source_available,
        flight_plan=flight_plan,
    )
    conn.execute(
        insert(db.assessments)
        .values(
            id=result["id"],
            input_digest=result["id"],
            owner_id=owner_id,
            launch_id=launch["id"],
            location_id=location["id"],
            revision=1,
            body=result,
            created_at=now,
        )
        .on_conflict_do_nothing()
    )
    conn.execute(
        insert(db.cache)
        .values(
            key=lookup, body={"assessment_id": result["id"]}, next_at=now + timedelta(seconds=60), failures=0
        )
        .on_conflict_do_update(
            index_elements=["key"],
            set_={"body": {"assessment_id": result["id"]}, "next_at": now + timedelta(seconds=60)},
        )
    )
    return conn.scalar(select(db.assessments.c.body).where(db.assessments.c.id == result["id"]))
