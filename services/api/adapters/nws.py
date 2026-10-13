from __future__ import annotations

import re
from datetime import timedelta

from packages.visibility.common import stamp, utc, finite


def valid_interval(value: str) -> tuple:
    start, end = value.split("/", 1)
    start = utc(start)
    if end.startswith("P"):
        match = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?", end)
        if not match:
            raise ValueError("Unsupported ISO duration")
        d, h, m, s = (float(x or 0) for x in match.groups())
        end = start + timedelta(days=d, hours=h, minutes=m, seconds=s)
    else:
        end = utc(end)
    if end <= start:
        raise ValueError("Empty forecast interval")
    return start, end


def normalize(payload: dict, provenance: dict, grid_id: str) -> list[dict]:
    props = payload["properties"]
    field = props.get("skyCover") or {}
    if field.get("uom") != "wmoUnit:percent":
        raise ValueError("Missing total cloud percent or unsupported units")
    fields = {}
    for name in ("skyCover", "visibility", "weather"):
        raw = props.get(name) or {}
        rows = []
        unit = raw.get("uom")
        if name == "visibility" and unit not in ("wmoUnit:m", "wmoUnit:km", "wmoUnit:mi", None):
            raise ValueError("Unsupported visibility unit")
        for value in raw.get("values", []):
            a, b = valid_interval(value["validTime"])
            v = value["value"]
            if v is not None and name != "weather":
                finite(v)
                if name == "visibility":
                    v *= {"wmoUnit:m": 1, "wmoUnit:km": 1000, "wmoUnit:mi": 1609.344}.get(unit, 1)
            rows.append((a, b, v))
        fields[name] = rows
    edges = sorted({t for rows in fields.values() for a, b, _ in rows for t in (a, b)})
    rows = []
    for a, b in zip(edges, edges[1:]):
        values = {k: [v for x, y, v in field_rows if x <= a and y >= b] for k, field_rows in fields.items()}
        clouds = values["skyCover"]
        if not clouds:
            continue
        total = None if any(v is None for v in clouds) else max(clouds)
        if total is not None and not 0 <= total <= 100:
            raise ValueError("Invalid cloud percentage")
        visibility = [v for v in values["visibility"] if v is not None]
        conditions = [item for batch in values["weather"] if batch for item in batch]
        fog = (
            any("fog" in str(item.get("weather", "")).lower() for item in conditions)
            if values["weather"]
            else None
        )
        rows.append(
            {
                "start": stamp(a),
                "end": stamp(b),
                "total": total,
                "visibility_m": min(visibility) if visibility else None,
                "fog": fog,
                "grid_id": grid_id,
                "provenance": [
                    {
                        **provenance,
                        "issued_at": stamp(utc(props["updateTime"])) if props.get("updateTime") else None,
                    }
                ],
                "missing_flags": ["cloud_layers_unavailable"] + ([] if visibility else ["haze_unknown"]),
            }
        )
    return rows
