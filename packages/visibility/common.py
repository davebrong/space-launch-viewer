"""Shared units and serialization; never obtains time implicitly in calculations."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from typing import Any


def utc(value: str | datetime) -> datetime:
    value = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("UTC-aware datetime required")
    return value.astimezone(timezone.utc)


def stamp(value: datetime) -> str:
    return utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def finite(*values: float) -> None:
    if any(isinstance(v, bool) or not math.isfinite(v) for v in values):
        raise ValueError("Finite numbers required")


def point(latitude_deg: float, longitude_deg: float, altitude_m: float = 0) -> dict:
    finite(latitude_deg, longitude_deg, altitude_m)
    if not -90 <= latitude_deg <= 90 or not -180 <= longitude_deg <= 180:
        raise ValueError("Coordinate out of range")
    return dict(
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        altitude_m=altitude_m,
        frame="WGS84_GEODETIC",
        altitude_datum="WGS84_ELLIPSOID",
    )
