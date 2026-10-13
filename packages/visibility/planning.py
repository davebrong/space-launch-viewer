"""Explicit nominal scenarios for planning, separate from evidence-admitted forecasts.

These are authored model assumptions, not recovered telemetry or published paths.
No observations, actual liftoff, or post-liftoff weather enter the scenario.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timedelta
from math import ceil, floor
import re

from geographiclib.geodesic import Geodesic

from .common import digest, stamp, utc
from .ensemble import envelope, evaluate_candidate
from .nearby import calculate_nearby, MANIFEST as NEARBY_MANIFEST

VERSION = "dragon-iss-nominal-v1"
# Assumed elapsed seconds, WGS84 altitude meters, geodesic downrange meters.
# A coarse nine-minute ascent, intentionally not a flight-dynamics simulation.
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
HEADINGS_DEG = (40, 45, 50)
ALTITUDE_SCALES = (0.85, 1.0, 1.15)
MANIFEST = {
    "version": VERSION,
    "knots_s_altitude_m_downrange_m": KNOTS,
    "initial_bearings_deg": HEADINGS_DEG,
    "altitude_scales": ALTITUDE_SCALES,
    "watch_padding_s": 120,
    "assumptions": [
        "Assume a northeast, non-dogleg Falcon 9 / Dragon ascent toward the ISS.",
        "Try initial headings of 40, 45 and 50 degrees and nominal heights varied by 15%.",
        "Interpolate an authored altitude/downrange profile through nine minutes after scheduled liftoff.",
        "Treat ascent engines as luminous from T+3 to T+9 minutes; omit later plume drift and booster return.",
        "Use WGS84 horizon geometry; add two minutes either side as a practical watch buffer.",
        "This is a planning simulation, not a mission-specific predicted trajectory or detection guarantee.",
    ],
    "references": [
        {
            "title": "NASA: typical Dragon launch sequence (Crew-1)",
            "url": "https://www.nasa.gov/wp-content/uploads/2021/05/crew-1_timeline_nov15.pdf",
            "supports": "An example of roughly nine minutes to second-stage cutoff; not the modeled height or route.",
        },
        {
            "title": "NASA: CRS-35 destination and launch site",
            "url": "https://science.nasa.gov/missions/station/nasas-spacex-crs-35-mission-to-launch-health-research/",
            "supports": "Prelaunch mission family context only; model coordinates are assumptions.",
        },
    ],
}
MODEL_SHA256 = digest({"trajectory": MANIFEST, "nearby": NEARBY_MANIFEST})


def supported(launch: dict) -> bool:
    pad = launch["pad_point"]
    station = "international space station" in (launch.get("mission_class") or "").lower()
    dragon = bool(re.search(r"dragon.*(?:crs|crew-\d)", launch["name"], re.I))
    return (
        (launch.get("vehicle_variant") or "").startswith("Falcon 9")
        and (station or dragon)
        and 28 <= pad["latitude_deg"] <= 29
        and -81 <= pad["longitude_deg"] <= -80
        and launch["time_precision"] == "exact"
        and bool(launch["net"])
        and not launch["disabled"]
        and launch["status"] not in ("hold", "scrubbed", "cancelled")
    )


def calculate_plan(launch: dict, location: dict, weather: list[dict], now: datetime) -> dict | None:
    nearby = calculate_nearby(launch, location, weather, now)
    if nearby:
        return nearby
    if not supported(launch):
        return None
    at = utc(launch["net"])
    pad = launch["pad_point"]
    candidates = []
    for heading in HEADINGS_DEG:
        for scale in ALTITUDE_SCALES:
            samples = []
            for t in range(180, 541, 5):
                j = min(bisect_right([k[0] for k in KNOTS], t) - 1, len(KNOTS) - 2)
                a, b = KNOTS[j : j + 2]
                weight = (t - a[0]) / (b[0] - a[0])
                altitude_m = (a[1] + weight * (b[1] - a[1])) * scale
                downrange_m = a[2] + weight * (b[2] - a[2])
                pos = Geodesic.WGS84.Direct(pad["latitude_deg"], pad["longitude_deg"], heading, downrange_m)
                samples.append(
                    {
                        "t_s": t,
                        "stage": 2,
                        "latitude_deg": pos["lat2"],
                        "longitude_deg": pos["lon2"],
                        "altitude_m": altitude_m,
                        "active_engine": True,
                        "active_plume": False,
                        "segment_id": "nominal-ascent",
                    }
                )
            candidate = evaluate_candidate(samples, location["point"], at, solar=False)
            candidate["id"] = f"{VERSION}:{heading}:{scale}"
            candidates.append(candidate)
    windows = envelope(candidates, at)
    watch = None
    directions = []
    if windows:
        start_s = max(0, floor((min(w["t_start_s"] for w in windows) - 120) / 60) * 60)
        end_s = ceil((max(w["t_end_s"] for w in windows) + 120) / 60) * 60
        # Minute rounding happens after applying the schedule, including its seconds.
        start = (at + timedelta(seconds=start_s)).replace(second=0, microsecond=0)
        end = at + timedelta(seconds=end_s)
        if end.second or end.microsecond:
            end = end.replace(second=0, microsecond=0) + timedelta(minutes=1)
        watch = {"start": stamp(start), "end": stamp(end)}
        nominal = candidates[4]["samples"]
        visible = [s for s in nominal if s["eligible"] and s["azimuth_deg"] is not None]
        if not visible:
            visible = [
                s for c in candidates for s in c["samples"] if s["eligible"] and s["azimuth_deg"] is not None
            ]
        for sample in visible:
            direction = (
                "north",
                "northeast",
                "east",
                "southeast",
                "south",
                "southwest",
                "west",
                "northwest",
            )[floor((sample["azimuth_deg"] + 22.5) / 45) % 8]
            if not directions or directions[-1] != direction:
                directions.append(direction)
    cutoff = min(at, now)
    forecast_rows = [
        r
        for r in weather
        if watch
        and utc(r["start"]) < utc(watch["end"])
        and utc(r["end"]) > utc(watch["start"])
        and r["provenance"]
        and all(
            p.get("issued_at") and utc(p["issued_at"]) <= cutoff and utc(p["fetched_at"]) <= cutoff
            for p in r["provenance"]
        )
    ]
    totals = [r["total"] for r in forecast_rows if r["total"] is not None]
    return {
        "model_version": VERSION,
        "model_sha256": MODEL_SHA256,
        "label": "Simulated viewing plan",
        "launch_time": stamp(at),
        "watch_interval": watch,
        "directions": list(dict.fromkeys(directions)),
        "windows": windows,
        "cloud_cover_min_pct": min(totals) if totals else None,
        "cloud_cover_max_pct": max(totals) if totals else None,
        "weather_basis": "archived_prelaunch" if totals else "unavailable",
        "assumptions": MANIFEST["assumptions"],
        "references": MANIFEST["references"],
        "uses_actual_liftoff": False,
        "uses_sightings": False,
    }
