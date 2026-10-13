"""WGS84 observer geometry. All distances are explicit meters, angles degrees."""

from __future__ import annotations

from math import atan2, cos, degrees, hypot, radians, sin, sqrt
from collections.abc import Sequence

from .common import finite, point

A_M = 6378137.0
F = 1 / 298.257223563
B_M = A_M * (1 - F)


def ecef(latitude_deg: float, longitude_deg: float, altitude_m: float) -> tuple[float, float, float]:
    point(latitude_deg, longitude_deg, altitude_m)
    lat, lon = radians(latitude_deg), radians(longitude_deg)
    e2 = F * (2 - F)
    n = A_M / sqrt(1 - e2 * sin(lat) ** 2)
    return (
        (n + altitude_m) * cos(lat) * cos(lon),
        (n + altitude_m) * cos(lat) * sin(lon),
        (n * (1 - e2) + altitude_m) * sin(lat),
    )


def intersects_earth(
    origin: Sequence[float],
    direction: Sequence[float],
    *,
    max_t: float | None = None,
    a_m: float = A_M,
    b_m: float = B_M,
) -> bool:
    axes = (a_m, a_m, b_m)
    o = [x / a for x, a in zip(origin, axes)]
    d = [x / a for x, a in zip(direction, axes)]
    aa = sum(x * x for x in d)
    bb = 2 * sum(x * y for x, y in zip(o, d))
    cc = sum(x * x for x in o) - 1
    disc = bb * bb - 4 * aa * cc
    if aa == 0 or disc < 0:
        return False
    roots = ((-bb - sqrt(disc)) / (2 * aa), (-bb + sqrt(disc)) / (2 * aa))
    lower = max(roots[0], 1e-8)
    upper = min(roots[1], max_t - 1e-8) if max_t is not None else roots[1]
    return upper >= lower


def geometry(observer_lat_lon_alt_m: Sequence[float], target_lat_lon_alt_m: Sequence[float]) -> dict:
    o, p = ecef(*observer_lat_lon_alt_m), ecef(*target_lat_lon_alt_m)
    dx, dy, dz = (p[i] - o[i] for i in range(3))
    lat, lon = map(radians, observer_lat_lon_alt_m[:2])
    east = -sin(lon) * dx + cos(lon) * dy
    north = -sin(lat) * cos(lon) * dx - sin(lat) * sin(lon) * dy + cos(lat) * dz
    up = cos(lat) * cos(lon) * dx + cos(lat) * sin(lon) * dy + sin(lat) * dz
    distance = sqrt(dx * dx + dy * dy + dz * dz)
    if distance < 1e-6:
        raise ValueError("Observer and target coincide")
    return {
        "azimuth_deg": degrees(atan2(east, north)) % 360 if hypot(east, north) > 1e-6 else None,
        "elevation_deg": degrees(atan2(up, hypot(east, north))),
        "range_m": distance,
        "occulted": intersects_earth(o, (dx, dy, dz), max_t=1),
    }


def earth_shadow(
    target_ecef_m: Sequence[float],
    sun_direction_ecef_unit: Sequence[float],
    earth_a_m: float = A_M,
    earth_b_m: float = B_M,
) -> bool:
    finite(*target_ecef_m, *sun_direction_ecef_unit)
    return intersects_earth(target_ecef_m, sun_direction_ecef_unit, a_m=earth_a_m, b_m=earth_b_m)
