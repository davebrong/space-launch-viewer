"""Skyfield uses only bundled ephemeris and timescale assets; no downloads."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from skyfield import almanac
from skyfield.api import Loader, load_file, wgs84
from skyfield.framelib import itrs
from skyfield_data import get_skyfield_data_path

from .common import utc, stamp


@lru_cache(maxsize=1)
def assets() -> tuple:
    directory = Path(get_skyfield_data_path())
    loader = Loader(str(directory))
    kernel = directory / "de421.bsp"
    return (
        loader.timescale(builtin=True),
        load_file(str(kernel)),
        hashlib.sha256(kernel.read_bytes()).hexdigest(),
    )


def model_manifest() -> dict:
    _, eph, sha = assets()
    segments = eph.spk.segments
    return {
        "version": "skyfield-" + version("skyfield"),
        "sha256": sha,
        "start_jd": max(s.start_jd for s in segments),
        "end_jd": min(s.end_jd for s in segments),
        "convention": "geometric solar center -0.833 deg; point-Sun ellipsoid shadow",
    }


def twilight_label(sun_deg: float) -> str:
    for threshold, label in ((-0.833, "daylight"), (-6, "civil"), (-12, "nautical"), (-18, "astronomical")):
        if sun_deg >= threshold:
            return label
    return "night"


def solar_at(at: datetime, latitude_deg: float, longitude_deg: float, altitude_m: float = 0) -> dict:
    ts, eph, _ = assets()
    t = ts.from_datetime(utc(at))
    observer = eph["earth"] + wgs84.latlon(latitude_deg, longitude_deg, elevation_m=altitude_m)
    elevation = float(observer.at(t).observe(eph["sun"]).apparent().altaz()[0].degrees)
    vector = eph["earth"].at(t).observe(eph["sun"]).frame_xyz(itrs).m
    return {
        "observer_sun_deg": elevation,
        "phase": twilight_label(elevation),
        "sun_direction_ecef_unit": (vector / np.linalg.norm(vector)).tolist(),
    }


@lru_cache(maxsize=8)
def solar_series(
    times: tuple[datetime, ...], latitude_deg: float, longitude_deg: float, altitude_m: float
) -> list[dict]:
    ts, eph, _ = assets()
    t = ts.from_datetimes([utc(at) for at in times])
    observer = eph["earth"] + wgs84.latlon(latitude_deg, longitude_deg, elevation_m=altitude_m)
    angles = observer.at(t).observe(eph["sun"]).apparent().altaz()[0].degrees
    vectors = eph["earth"].at(t).observe(eph["sun"]).frame_xyz(itrs).m
    vectors /= np.linalg.norm(vectors, axis=0)
    return [
        {"observer_sun_deg": float(angle), "sun_direction_ecef_unit": vector.tolist()}
        for angle, vector in zip(angles, vectors.T)
    ]


@lru_cache(maxsize=512)
def solar_events(
    local_date: str,
    timezone: str,
    latitude_deg: float,
    longitude_deg: float,
    altitude_m: float = 0,
    sunrise_center_deg: float = -0.833,
) -> dict:
    ts, eph, _ = assets()
    start = datetime.fromisoformat(local_date).replace(tzinfo=ZoneInfo(timezone))
    t0, t1 = ts.from_datetime(start), ts.from_datetime(start + timedelta(days=1))
    location = wgs84.latlon(latitude_deg, longitude_deg, elevation_m=altitude_m)
    transitions = []
    for angle, name in ((sunrise_center_deg, "sun"), (-6, "civil"), (-12, "nautical"), (-18, "astronomical")):
        f = almanac.risings_and_settings(eph, eph["sun"], location, horizon_degrees=angle, radius_degrees=0)
        times, states = almanac.find_discrete(t0, t1, f)
        for at, rising in zip(times, states):
            transitions.append(
                {
                    "at": stamp(at.utc_datetime()),
                    "event": ("sunrise" if rising else "sunset") if name == "sun" else name,
                    "direction": "rising" if rising else "setting",
                }
            )
    transitions.sort(key=lambda r: r["at"])
    rise = next((r["at"] for r in transitions if r["event"] == "sunrise"), None)
    setting = next((r["at"] for r in transitions if r["event"] == "sunset"), None)
    state = (
        "normal"
        if rise and setting
        else "no_rise_or_set"
        if not rise and not setting
        else "no_rise"
        if not rise
        else "no_set"
    )
    return {
        "local_date": local_date,
        "timezone": timezone,
        "sunrise": rise,
        "sunset": setting,
        "rise_set_state": state,
        "transitions": transitions,
    }
