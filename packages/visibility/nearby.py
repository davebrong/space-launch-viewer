"""Pad-relative early-ascent planning; no mission track or timed height is inferred."""

from datetime import datetime, timedelta
from math import floor

from geographiclib.geodesic import Geodesic

from .common import digest, stamp, utc
from .geometry import geometry
from .weather import fresh

MANIFEST = {
    "version": "nearby-pad-v1",
    "maximum_distance_m": 100000,
    "reference_height_m": 2000,
    "watch_before_s": 120,
    "watch_after_s": 300,
    "assumptions": [
        "Nearby Cape/Kennedy launches are potential early-ascent viewing opportunities regardless of mission family.",
        "This model covers points within 100 km of a known pad, with an unobstructed WGS84 sightline to a reference point 2 km above it. These are model coverage choices, not measured visibility limits.",
        "The direction points toward the launch pad. It is not a predicted flight path; the rocket moves away during ascent.",
        "Be ready two minutes before scheduled liftoff and watch for five minutes afterward. This is practical watch guidance, not a calculated visible duration.",
        "Trees, buildings, haze and clouds can obscure the ascent. Use an open horizon; visibility is not guaranteed.",
    ],
    "references": [
        {
            "title": "NASA: viewing launches around Kennedy",
            "url": "https://www.nasa.gov/kennedy/see-a-launch-up-close/",
            "supports": "Regional launch-viewing context, not this model's distance limit or watch duration.",
        }
    ],
}


def calculate_nearby(launch: dict, location: dict, weather: list[dict], now: datetime) -> dict | None:
    pad, observer = launch["pad_point"], location["point"]
    if (
        launch["disabled"]
        or launch["status"] in ("hold", "scrubbed", "cancelled")
        or not launch.get("pad_name")
        or "unknown" in launch["pad_name"].lower()
        or not (28 <= pad["latitude_deg"] <= 29 and -81 <= pad["longitude_deg"] <= -80)
        or launch["time_precision"] not in ("exact", "window", "date")
    ):
        return None
    inverse = Geodesic.WGS84.Inverse(
        observer["latitude_deg"], observer["longitude_deg"], pad["latitude_deg"], pad["longitude_deg"]
    )
    if inverse["s12"] > MANIFEST["maximum_distance_m"]:
        return None
    sightline = geometry(
        (observer["latitude_deg"], observer["longitude_deg"], observer["altitude_m"]),
        (pad["latitude_deg"], pad["longitude_deg"], pad["altitude_m"] + MANIFEST["reference_height_m"]),
    )
    if sightline["occulted"] or sightline["elevation_deg"] <= 0:
        return None
    watch, at = None, None
    if launch["time_precision"] == "exact" and launch.get("net"):
        at = utc(launch["net"])
        start, end = at, at
    elif launch["time_precision"] == "window" and launch.get("window"):
        start, end = utc(launch["window"]["start"]), utc(launch["window"]["end"])
        at = start
    elif launch["time_precision"] == "date" and launch.get("date_label"):
        start = end = None
    else:
        return None
    if at:
        watch = {
            "start": stamp(start - timedelta(seconds=MANIFEST["watch_before_s"])),
            "end": stamp(end + timedelta(seconds=MANIFEST["watch_after_s"])),
        }
    cutoff = min(at, now) if at else now
    totals = [
        r["total"]
        for r in weather
        if watch
        and utc(r["start"]) < utc(watch["end"])
        and utc(r["end"]) > utc(watch["start"])
        and r.get("provenance")
        and "provider_refresh_failed" not in r.get("missing_flags", [])
        and r.get("total") is not None
        and all(
            p.get("issued_at")
            and utc(p["issued_at"]) <= cutoff
            and utc(p["fetched_at"]) <= cutoff
            and fresh(
                (cutoff - utc(p["fetched_at"])).total_seconds(),
                (cutoff - utc(p["issued_at"])).total_seconds(),
                True,
            )
            for p in r["provenance"]
        )
    ]
    bearing = inverse["azi1"] % 360
    direction = ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")[
        floor((bearing + 22.5) / 45) % 8
    ]
    return {
        "kind": "near_launch_site",
        "model_version": MANIFEST["version"],
        "model_sha256": digest(MANIFEST),
        "label": "Nearby launch estimate",
        "launch_time": stamp(at) if at else None,
        "watch_interval": watch,
        "directions": [direction],
        "windows": [],
        "pad_distance_m": inverse["s12"],
        "pad_bearing_deg": bearing,
        "cloud_cover_min_pct": min(totals) if totals else None,
        "cloud_cover_max_pct": max(totals) if totals else None,
        "weather_basis": "archived_prelaunch" if totals else "unavailable",
        "assumptions": MANIFEST["assumptions"],
        "references": MANIFEST["references"],
        "uses_actual_liftoff": False,
        "uses_sightings": False,
    }
