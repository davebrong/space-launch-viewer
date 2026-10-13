from __future__ import annotations

import json
from pathlib import Path

from packages.visibility.common import finite


def parse_archive(series_path: str | Path, events_path: str | Path) -> dict:
    series = json.loads(Path(series_path).read_text())
    events = json.loads(Path(events_path).read_text())
    required = ("time", "altitude", "downrange_distance")
    if not all(isinstance(series.get(k), list) for k in required):
        raise ValueError("Unsupported historical format")
    count = len(series["time"])
    if count < 2 or any(len(series[k]) != count for k in required):
        raise ValueError("Mismatched historical arrays")
    samples = []
    for t, altitude_km, downrange_km in zip(*(series[k] for k in required)):
        finite(t, altitude_km, downrange_km)
        if samples and t <= samples[-1]["t_s"]:
            raise ValueError("Non-monotone historical time")
        samples.append({"t_s": t, "altitude_m": altitude_km * 1000, "downrange_m": downrange_km * 1000})
    return {
        "sample_count": count,
        "last_t_s": samples[-1]["t_s"],
        "last_altitude_m": samples[-1]["altitude_m"],
        "last_downrange_m": samples[-1]["downrange_m"],
        "ses1_s": events.get("ses1"),
        "seco1_s": events.get("seco1"),
        "production_admitted": False,
        "samples": samples,
        "reasons": ["altitude_datum_unverified", "stage_identity_unverified", "compatibility_unverified"],
    }
