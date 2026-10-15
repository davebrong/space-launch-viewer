"""Clear-sky viewing estimates from mission-specific published route information.

No departure direction is inferred from vehicle family, payload, destination or
orbit. A distant observer receives an estimate only when an admitted source names
this mission's departure heading; the ascent height/downrange envelope remains an
explicit generic model assumption. The departure heading is the rocket's direction
from the pad; the observer's viewing direction is calculated separately.
No observations, actual liftoff, or post-liftoff weather enter the scenario.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timedelta
from math import ceil, floor

from geographiclib.geodesic import Geodesic

from .common import digest, stamp, utc
from .ensemble import bearing_sector, envelope, evaluate_candidate
from .nearby import calculate_nearby, MANIFEST as NEARBY_MANIFEST

VERSION = "published-heading-envelope-v2"
COMPASS_8 = ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")
# A generic two-stage ascent to a roughly 200 km parking orbit: elapsed seconds,
# WGS84 altitude meters, geodesic downrange meters. Not a vehicle or mission profile.
KNOTS = (
    (0, 0, 0),
    (60, 10000, 4000),
    (120, 40000, 35000),
    (180, 85000, 130000),
    (240, 120000, 300000),
    (300, 155000, 550000),
    (360, 185000, 880000),
    (420, 205000, 1270000),
    (480, 215000, 1700000),
    (540, 215000, 2160000),
)
ALTITUDE_SCALES = (0.85, 1.0, 1.15)
HEADING_STEPS = 5  # Evenly across the published sector, including both edges.
SAMPLE_STEP_S = 5
# Practical clear-sky threshold, not a measured detection limit: lower geometry is
# reported as horizon-grazing instead of a viewing opportunity.
MIN_USEFUL_ELEVATION_DEG = 3.0
MANIFEST = {
    "version": VERSION,
    "knots_s_altitude_m_downrange_m": KNOTS,
    "altitude_scales": ALTITUDE_SCALES,
    "heading_sweep": "five evenly spaced headings across the published sector, including both edges",
    "watch_padding_s": 120,
    "min_useful_elevation_deg": MIN_USEFUL_ELEVATION_DEG,
    "basis_assumptions": {
        "departure_heading": [
            "The departure direction comes from a published mission-specific source, named below. It is only a general compass direction, so five headings across its whole sector are evaluated.",
            "When published launch hazard areas exist for the mission, only headings that also point toward them are evaluated: toward every downrange area at once when they line up, otherwise toward any of them. Hazard areas are safety zones, not the flight path, so the whole remaining range is still evaluated.",
        ],
        "hazard_corridor": [
            "No source states this mission's departure direction. The direction comes from the mission's published launch hazard areas: the range of bearings from the pad that points toward every downrange area at once. Five headings across that whole range are evaluated.",
            "Hazard areas are safety zones for falling stages and debris, not the flight path. A straight ascent passes over them, but the rocket's exact track within the range is unknown, and doglegs would break this assumption.",
        ],
    },
    "assumptions": [
        "Height and distance flown are a generic nine-minute ascent to about 200 km, varied by 15%. This is not this rocket's actual profile; real vehicles and missions differ.",
        "The path is assumed to follow a straight geodesic from the pad in that direction. Doglegs, booster return and later plume drift are not modeled.",
        "Engines are assumed visible while above your horizon during the first nine minutes. Stage-separation gaps are ignored.",
        "Clear skies and an unobstructed horizon are assumed. Clouds, haze, trees and buildings can block the view.",
        "Paths that never rise 3 degrees above your horizon are reported as horizon-grazing, not as a viewing opportunity. Sunlit twilight plumes can sometimes be seen farther away; they are not modeled.",
        "This is a clear-sky planning estimate, not a measured trajectory or a promise that the launch will be seen.",
    ],
    "references": [
        {
            "title": "SpaceX Falcon user guide: sample ascent timelines",
            "url": "https://www.spacex.com/assets/media/falcon-users-guide-2025-05-09.pdf",
            "supports": "Example ascent duration context only; it states that individual mission profiles differ. Model heights are assumptions.",
        },
    ],
}
MODEL_SHA256 = digest({"trajectory": MANIFEST, "nearby": NEARBY_MANIFEST})


def compass_name(bearing_deg: float) -> str:
    return COMPASS_8[floor((bearing_deg % 360 + 22.5) / 45) % 8]


def usable_heading(flight_plan: dict | None) -> dict | None:
    """Return admitted heading evidence; stale headings stay usable but labeled."""
    if not flight_plan or flight_plan.get("state") not in ("found", "stale") or flight_plan.get("conflict"):
        return None
    headings = [e for e in flight_plan.get("evidence", []) if e.get("evidence_type") == "departure_heading"]
    if len(headings) != 1 or not headings[0].get("departure_sector_deg"):
        return None
    return headings[0]


def hazard_items(flight_plan: dict | None) -> list[dict]:
    return [
        e
        for e in (flight_plan or {}).get("evidence", [])
        if e.get("evidence_type") == "hazard_corridor" and e.get("hazard_bearing_sector_deg")
    ]


def hazard_sectors(flight_plan: dict | None) -> list[list[dict]]:
    """Narrowing options, tightest first: toward every area at once, then toward any area."""
    items = hazard_items(flight_plan)
    consistent = [e["hazard_consistent_sector_deg"] for e in items if e.get("hazard_consistent_sector_deg")]
    union = [e["hazard_bearing_sector_deg"] for e in items]
    return [option for option in (consistent, union) if option]


def usable_hazard(flight_plan: dict | None) -> dict | None:
    """Hazard-area direction evidence for a mission with no reported heading.

    Admitted only for one hazard notice whose downrange areas line up along a
    common bearing range; a notice with alternate or scattered areas gives none.
    """
    if not flight_plan or flight_plan.get("state") not in ("found", "stale") or flight_plan.get("conflict"):
        return None
    items = hazard_items(flight_plan)
    if len(items) != 1 or not items[0].get("hazard_consistent_sector_deg"):
        return None
    item = items[0]
    sector = item["hazard_consistent_sector_deg"]
    middle = sector["start_deg"] + ((sector["end_deg"] - sector["start_deg"]) % 360) / 2
    return {
        "evidence_type": "hazard_corridor",
        "departure_direction": compass_name(middle),
        "departure_sector_deg": sector,
        "source_name": item["source_name"],
        "source_url": item.get("chart_url") or item["source_url"],
        "fetched_at": item["fetched_at"],
        "stale": bool(item.get("stale")),
    }


def within(bearing_deg: float, sector: dict) -> bool:
    if sector["end_deg"] - sector["start_deg"] >= 360:
        return True
    start, end, b = sector["start_deg"] % 360, sector["end_deg"] % 360, bearing_deg % 360
    return start <= b <= end if start <= end else b >= start or b <= end


def swept_sector(heading: dict, options: list[list[dict]]) -> tuple[float, float, bool]:
    """Start and span of headings to evaluate.

    Published hazard areas narrow the reported sector to the bearings that also
    point toward them, using the tightest option that overlaps (see hazard_sectors).
    The hazard areas never define a centerline: the whole overlap is still swept.
    """
    start = heading["start_deg"]
    span = (heading["end_deg"] - start) % 360 or 360.0
    for hazards in options:
        inside = [d for d in range(int(span) + 1) if any(within(start + d, h) for h in hazards)]
        if inside:
            return (start + inside[0]) % 360, float(inside[-1] - inside[0]), True
    return start, span, False


def _samples(pad: dict, heading_deg: float, scale: float) -> list[dict]:
    times = [k[0] for k in KNOTS]
    rows = []
    line = Geodesic.WGS84.DirectLine(pad["latitude_deg"], pad["longitude_deg"], heading_deg, KNOTS[-1][2])
    for t in range(SAMPLE_STEP_S, KNOTS[-1][0] + 1, SAMPLE_STEP_S):
        j = min(bisect_right(times, t) - 1, len(KNOTS) - 2)
        a, b = KNOTS[j : j + 2]
        weight = (t - a[0]) / (b[0] - a[0])
        position = line.Position(a[2] + weight * (b[2] - a[2]))
        rows.append(
            {
                "t_s": t,
                "stage": 1,
                "latitude_deg": position["lat2"],
                "longitude_deg": position["lon2"],
                "altitude_m": (a[1] + weight * (b[1] - a[1])) * scale,
                "active_engine": True,
                "active_plume": False,
                "segment_id": "modeled-ascent",
            }
        )
    return rows


def _watch_reference(launch: dict) -> tuple[datetime | None, datetime | None]:
    if launch["time_precision"] == "exact" and launch.get("net"):
        at = utc(launch["net"])
        return at, at
    if launch["time_precision"] == "window" and launch.get("window"):
        return utc(launch["window"]["start"]), utc(launch["window"]["end"])
    return None, None


def _weather_summary(weather: list[dict], watch: dict | None, cutoff: datetime) -> list[float]:
    rows = [
        r
        for r in weather
        if watch
        and utc(r["start"]) < utc(watch["end"])
        and utc(r["end"]) > utc(watch["start"])
        and r.get("provenance")
        and "provider_refresh_failed" not in r.get("missing_flags", [])
        and all(
            p.get("issued_at") and utc(p["issued_at"]) <= cutoff and utc(p["fetched_at"]) <= cutoff
            for p in r["provenance"]
        )
    ]
    return [r["total"] for r in rows if r["total"] is not None]


def calculate_heading_plan(
    launch: dict,
    location: dict,
    weather: list[dict],
    now: datetime,
    evidence: dict,
    hazards: list[list[dict]] | None = None,
) -> dict | None:
    if launch["disabled"] or launch["status"] in ("hold", "scrubbed", "cancelled"):
        return None
    pad = launch["pad_point"]
    sector = evidence["departure_sector_deg"]
    first, span, narrowed = swept_sector(sector, hazards or [])
    headings = tuple(round((first + span * i / (HEADING_STEPS - 1)) % 360, 3) for i in range(HEADING_STEPS))
    observer = location["point"]
    candidates = []
    for heading in headings:
        for scale in ALTITUDE_SCALES:
            # Geometry only; clear-sky planning does not depend on lighting or clouds.
            candidate = evaluate_candidate(_samples(pad, heading, scale), observer, now, solar=False)
            candidate["id"] = f"{VERSION}:{heading:g}:{scale:g}"
            candidates.append(candidate)
    for candidate in candidates:
        candidate["windows"] = [
            w for w in candidate["windows"] if w["max_elevation_deg"] >= MIN_USEFUL_ELEVATION_DEG
        ]
    found = [w for c in candidates for w in c["windows"]]
    grazing = not found and any(
        s["eligible"] and s["elevation_deg"] > 0 for c in candidates for s in c["samples"]
    )
    relative = None
    directions: list[str] = []
    sector_seen = None
    elevations = None
    if found:
        relative = {
            "t_start_s": max(0, floor((min(w["t_start_s"] for w in found) - MANIFEST["watch_padding_s"]) / 60) * 60),
            "t_end_s": ceil((max(w["t_end_s"] for w in found) + MANIFEST["watch_padding_s"]) / 60) * 60,
        }
        def shown(candidate: dict) -> list[dict]:
            spans = [(w["t_start_s"], w["t_end_s"]) for w in candidate["windows"]]
            return [
                s
                for s in candidate["samples"]
                if s["eligible"] and s["azimuth_deg"] is not None and any(a <= s["t_s"] <= b for a, b in spans)
            ]

        # Lead with the central heading/height; otherwise the first candidate with a view.
        nominal = candidates[len(candidates) // 2]
        visible = shown(nominal) or next(shown(c) for c in candidates if c["windows"])
        for sample in visible:
            name = compass_name(sample["azimuth_deg"])
            if not directions or directions[-1] != name:
                directions.append(name)
        sector_seen = bearing_sector([b for w in found for b in w["bearings"]])
        elevations = {
            "min_deg": min(w["max_elevation_deg"] for w in found),
            "max_deg": max(w["max_elevation_deg"] for w in found),
        }
    agreement = {"with_view": sum(bool(c["windows"]) for c in candidates), "evaluated": len(candidates)}
    start, end = _watch_reference(launch)
    watch, windows = None, []
    if relative and start and end:
        watch_start = (start + timedelta(seconds=relative["t_start_s"])).replace(second=0, microsecond=0)
        watch_end = end + timedelta(seconds=relative["t_end_s"])
        if watch_end.second or watch_end.microsecond:
            watch_end = watch_end.replace(second=0, microsecond=0) + timedelta(minutes=1)
        watch = {"start": stamp(watch_start), "end": stamp(watch_end)}
        if launch["time_precision"] == "exact":
            # One row per modeled heading (its three heights merged), so different
            # headings are never blended into one misleading compass span.
            for i in range(0, len(candidates), len(ALTITUDE_SCALES)):
                windows += envelope(candidates[i : i + len(ALTITUDE_SCALES)], start)
    totals = _weather_summary(weather, watch, min(start, now) if start else now)
    basis = evidence["evidence_type"]
    return {
        "kind": "published_heading_model",
        "model_version": VERSION,
        "model_sha256": MODEL_SHA256,
        "label": "Clear-sky estimate from published hazard areas"
        if basis == "hazard_corridor"
        else "Clear-sky estimate from published heading",
        "launch_time": stamp(start) if start and launch["time_precision"] == "exact" else None,
        "watch_interval": watch,
        "relative_window": relative,
        "horizon_grazing": grazing,
        "candidates": agreement,
        "directions": list(dict.fromkeys(directions)),
        "viewing_sector": sector_seen,
        "max_elevation_deg": elevations,
        "windows": windows,
        "route_basis": {
            "evidence_type": evidence["evidence_type"],
            "departure_direction": evidence["departure_direction"],
            "departure_sector_deg": sector,
            "swept_sector_deg": {"start_deg": first, "end_deg": (first + span) % 360 if span < 360 else first},
            "narrowed_by_hazard_areas": narrowed,
            "source_name": evidence["source_name"],
            "source_url": evidence["source_url"],
            "fetched_at": evidence["fetched_at"],
            "stale": evidence.get("stale", False),
        },
        "clear_sky_assumed": True,
        "cloud_cover_min_pct": min(totals) if totals else None,
        "cloud_cover_max_pct": max(totals) if totals else None,
        "weather_basis": "archived_prelaunch" if totals else "unavailable",
        "assumptions": MANIFEST["basis_assumptions"][basis] + MANIFEST["assumptions"],
        "references": MANIFEST["references"],
        "uses_actual_liftoff": False,
        "uses_sightings": False,
    }


def calculate_plan(
    launch: dict, location: dict, weather: list[dict], now: datetime, flight_plan: dict | None = None
) -> dict | None:
    """Published mission heading first, then a direction from lined-up published hazard
    areas, then pad-relative nearby guidance, else nothing."""
    evidence = usable_heading(flight_plan)
    if evidence:
        evidence = {**evidence, "stale": bool(evidence.get("stale"))}
        plan = calculate_heading_plan(launch, location, weather, now, evidence, hazard_sectors(flight_plan))
        if plan:
            return plan
    elif hazard := usable_hazard(flight_plan):
        plan = calculate_heading_plan(launch, location, weather, now, hazard)
        if plan:
            return plan
    return calculate_nearby(launch, location, weather, now)
