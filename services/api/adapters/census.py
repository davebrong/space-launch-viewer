from __future__ import annotations

import csv
import io
import re
import zipfile
from functools import lru_cache
from pathlib import Path

from services.api.config import ROOT


@lru_cache(maxsize=4)
def gazetteer(path: str) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.endswith(".txt")]
        if len(names) != 1:
            raise ValueError("Unsupported Census archive")
        text = archive.read(names[0]).decode("utf-8-sig")
    rows = csv.DictReader(io.StringIO(text), delimiter="|")
    if not {"GEOID", "INTPTLAT", "INTPTLONG"}.issubset({h.strip() for h in rows.fieldnames or []}):
        raise ValueError("Unsupported Census headers")
    result = {}
    for row in rows:
        row = {k.strip(): v.strip() for k, v in row.items()}
        result[row["GEOID"]] = (float(row["INTPTLAT"]), float(row["INTPTLONG"]))
    return result


def resolve_zip(zip: str, path: str | Path | None = None) -> dict:
    if not isinstance(zip, str) or not re.fullmatch(r"[0-9]{5}", zip):
        return {"error": "INVALID_INPUT"}
    path = path or ROOT / "data/gazetteer/census-2025.zip"
    found = gazetteer(str(path)).get(zip)
    if not found:
        return {"status": "unavailable", "fallback": ["gps", "manual"]}
    return {"zip": zip, "latitude_deg": found[0], "longitude_deg": found[1], "confirmed": False}


@lru_cache(maxsize=1)
def timezone_resolver():
    from timezonefinder import TimezoneFinder

    return TimezoneFinder()


def timezone_at(latitude_deg: float, longitude_deg: float) -> str | None:
    return timezone_resolver().timezone_at(lat=latitude_deg, lng=longitude_deg)
