"""Geodesic reconstruction from independently published vertices; never hazard centers."""

from __future__ import annotations

from bisect import bisect_right
from datetime import timedelta
from math import ceil, floor

from geographiclib.geodesic import Geodesic

from .common import utc, stamp
from .geometry import geometry, ecef, earth_shadow
from .astronomy import solar_series
from .time import round_window


def bearing_sector(bearings_deg: list[float]) -> dict | None:
    values = sorted({b % 360 for b in bearings_deg if b is not None})
    if not values:
        return None
    gaps = [
        (
            values[(i + 1) % len(values)] + (360 if i == len(values) - 1 else 0) - b,
            values[(i + 1) % len(values)],
            b,
        )
        for i, b in enumerate(values)
    ]
    _, start, end = min(gaps, key=lambda g: (-g[0], g[1]))
    raw_span = (end - start) % 360
    low = floor(start / 15) * 15
    high = ceil((start + raw_span) / 15) * 15
    if high - low >= 360:
        return {"start_deg": 0, "end_deg": 360, "wraps_north": False}
    return {"start_deg": low, "end_deg": high % 360, "wraps_north": high >= 360}


def route_point(vertices: list[dict], downrange_m: float) -> tuple[float, float]:
    remaining = downrange_m
    for a, b in zip(vertices, vertices[1:]):
        line = Geodesic.WGS84.InverseLine(
            a["latitude_deg"], a["longitude_deg"], b["latitude_deg"], b["longitude_deg"]
        )
        if remaining <= line.s13:
            p = line.Position(remaining)
            return p["lat2"], p["lon2"]
        remaining -= line.s13
    raise ValueError("profile_exceeds_published_path")


def reconstruct(profile: dict, route: dict) -> list[dict]:
    if route.get("evidence_type") != "published_path" or route.get("dogleg") != "absent_supported":
        raise ValueError("No supported flight path")
    output = []
    stages_started = set()
    for burn_index, burn in enumerate(
        sorted(profile["powered_intervals"], key=lambda b: (b["start_s"], b["stage"]))
    ):
        stage = burn["stage"]
        if stage not in (1, 2):
            raise ValueError("unsupported_stage")
        if stage in stages_started:
            continue  # Only the first source-supported ascent burn of each stage.
        stages_started.add(stage)
        samples = sorted((s for s in profile["samples"] if s["stage"] == stage), key=lambda r: r["t_s"])
        times = [s["t_s"] for s in samples]
        if len(times) < 2 or len(set(times)) != len(times) or burn["end_s"] <= burn["start_s"]:
            raise ValueError("Invalid stage coverage")
        target_times = {burn["start_s"], burn["end_s"]}
        target_times.update(range(ceil(burn["start_s"] / 5) * 5, floor(burn["end_s"] / 5) * 5 + 1, 5))
        segment = 0
        for t in sorted(target_times):
            j = bisect_right(times, t) - 1
            if j < 0 or j >= len(samples):
                segment += 1
                continue
            a = samples[j]
            if a["t_s"] == t:
                alt, distance = a["altitude_m"], a["downrange_m"]
            elif j + 1 < len(samples) and samples[j + 1]["t_s"] - a["t_s"] <= 15:
                b = samples[j + 1]
                weight = (t - a["t_s"]) / (b["t_s"] - a["t_s"])
                alt = a["altitude_m"] + weight * (b["altitude_m"] - a["altitude_m"])
                distance = a["downrange_m"] + weight * (b["downrange_m"] - a["downrange_m"])
            else:
                segment += 1
                continue
            lat, lon = route_point(route["path_vertices"], distance)
            output.append(
                {
                    "t_s": t,
                    "stage": stage,
                    "latitude_deg": lat,
                    "longitude_deg": lon,
                    "altitude_m": alt,
                    "active_engine": burn["emission"] == "active_engine",
                    "active_plume": burn["emission"] == "active_plume",
                    "segment_id": f"{burn_index}:{segment}",
                }
            )
    return output


def evaluate_candidate(samples: list[dict], observer: dict, t0, *, solar: bool = True) -> dict:
    t0 = utc(t0)
    op = [observer[k] for k in ("latitude_deg", "longitude_deg", "altitude_m")]
    evaluated = []
    lighting = (
        solar_series(tuple(t0 + timedelta(seconds=row["t_s"]) for row in samples), *op)
        if solar and samples
        else [None] * len(samples)
    )
    for row, light in zip(samples, lighting):
        geo = geometry(op, [row[k] for k in ("latitude_deg", "longitude_deg", "altitude_m")])
        shadow = (
            earth_shadow(
                ecef(row["latitude_deg"], row["longitude_deg"], row["altitude_m"]),
                light["sun_direction_ecef_unit"],
            )
            if light
            else None
        )
        evaluated.append(
            {
                **row,
                **geo,
                "observer_sun_deg": light["observer_sun_deg"] if light else None,
                "in_shadow": shadow,
                "eligible": geo["elevation_deg"] > 0
                and not geo["occulted"]
                and (row["active_engine"] or row["active_plume"]),
            }
        )
    windows = []
    current = []

    def flush() -> None:
        if len(current) >= 2 and current[-1]["t_s"] - current[0]["t_s"] >= 20:
            bearings = [p["azimuth_deg"] for p in current if p["azimuth_deg"] is not None]
            names = (
                "N",
                "NNE",
                "NE",
                "ENE",
                "E",
                "ESE",
                "SE",
                "SSE",
                "S",
                "SSW",
                "SW",
                "WSW",
                "W",
                "WNW",
                "NW",
                "NNW",
            )
            movement = (
                (names[round(bearings[0] / 22.5) % 16] + " toward " + names[round(bearings[-1] / 22.5) % 16])
                if bearings
                else "Through zenith; bearing undefined"
            )
            movement += "; " + (
                "rising" if current[-1]["elevation_deg"] > current[0]["elevation_deg"] else "descending"
            )
            windows.append(
                {
                    "t_start_s": current[0]["t_s"],
                    "t_end_s": current[-1]["t_s"],
                    "bearings": [p["azimuth_deg"] for p in current if p["azimuth_deg"] is not None],
                    "max_elevation_deg": max(p["elevation_deg"] for p in current),
                    "movement": movement,
                }
            )

    lighting_start = None
    flag = False
    previous = None
    for row in evaluated:
        continuity = (
            previous is not None
            and row["segment_id"] == previous["segment_id"]
            and row["stage"] == previous["stage"]
            and row["t_s"] - previous["t_s"] <= 15
        )
        crossing = None
        if continuity and row["eligible"] != previous["eligible"]:
            a, b = previous["elevation_deg"], row["elevation_deg"]
            if a * b <= 0 and a != b:
                weight = -a / (b - a)
                crossing = {
                    **row,
                    "t_s": previous["t_s"] + weight * (row["t_s"] - previous["t_s"]),
                    "elevation_deg": 0.0,
                }
                if previous["azimuth_deg"] is not None and row["azimuth_deg"] is not None:
                    delta = (row["azimuth_deg"] - previous["azimuth_deg"] + 180) % 360 - 180
                    crossing["azimuth_deg"] = (previous["azimuth_deg"] + weight * delta) % 360
        if crossing and not row["eligible"]:
            current.append(crossing)
        if not continuity or not row["eligible"]:
            flush()
            current = []
        if row["eligible"]:
            if crossing:
                current.append(crossing)
            current.append(row)
        good_light = (
            row["eligible"]
            and row["elevation_deg"] >= 5
            and row["observer_sun_deg"] is not None
            and row["observer_sun_deg"] <= -6
        )
        if not continuity or not good_light:
            lighting_start = row["t_s"] if good_light else None
        elif lighting_start is not None and row["t_s"] - lighting_start >= 60:
            flag = True
        previous = row
    flush()
    return {
        "windows": windows,
        "samples": evaluated,
        "lighting_flag": flag,
        "all_below_horizon": bool(evaluated)
        and all(p["elevation_deg"] <= 0 or p["occulted"] for p in evaluated),
    }


def envelope(candidates: list[dict], t0) -> list[dict]:
    rows = sorted(
        [{**w, "candidate_ids": [c["id"]]} for c in candidates for w in c["windows"]],
        key=lambda w: w["t_start_s"],
    )
    merged = []
    for row in rows:
        if merged and row["t_start_s"] <= merged[-1]["t_end_s"]:
            old = merged[-1]
            old["t_end_s"] = max(old["t_end_s"], row["t_end_s"])
            old["candidate_ids"] = sorted(set(old["candidate_ids"] + row["candidate_ids"]))
            old["bearings"].extend(row["bearings"])
            old["elevations"].append(row["max_elevation_deg"])
            old["movements"].append(row["movement"])
        else:
            merged.append({**row, "elevations": [row["max_elevation_deg"]], "movements": [row["movement"]]})
    result = []
    for row in merged:
        sector = bearing_sector(row["bearings"])
        result.append(
            {
                "interval": round_window(
                    stamp(utc(t0) + timedelta(seconds=row["t_start_s"])),
                    stamp(utc(t0) + timedelta(seconds=row["t_end_s"])),
                ),
                "t_start_s": row["t_start_s"],
                "t_end_s": row["t_end_s"],
                "candidate_ids": row["candidate_ids"],
                "bearing_sectors": [sector] if sector else [],
                "max_elevation_min_deg": min(row["elevations"]),
                "max_elevation_max_deg": max(row["elevations"]),
                "movement": "; ".join(sorted(set(row["movements"]))),
                "rounded_for_display": True,
            }
        )
    return result
