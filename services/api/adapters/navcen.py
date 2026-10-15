"""US Coast Guard NAVCEN SOLAR launch hazard areas: mission-named hazard corridors.

SOLAR publishes Broadcast Notice to Mariners launch hazard areas as a GeoJSON
FeatureCollection assigned to a JavaScript variable. The file is parsed strictly as
JSON data and never executed. Hazard areas are safety zones for falling stages and
debris; they are NOT a flight path, centerline, altitude profile or timing. This
adapter only reports where the published areas lie relative to the pad.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from geographiclib.geodesic import Geodesic

from packages.visibility.ensemble import bearing_sector

VERSION = "navcen-solar-hazard-v2"
SOURCE_NAME = "US Coast Guard NAVCEN SOLAR"
SOLAR_URL = "https://www.navcen.uscg.gov/sites/default/files/tmp/test.js"
CHART_URL = "https://www.navcen.uscg.gov/chart"
ROBOTS_URL = "https://www.navcen.uscg.gov/robots.txt"
TERMS_NOTE = "US Government work (17 U.S.C. 105). Broadcast Notice to Mariners hazard areas via the NAVCEN SOLAR chart."
MONTHS = {m: i + 1 for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"))}
WINDOW = re.compile(r"(\d{2})/(\d{2})(\d{2}) ([A-Z]{3}) (\d{2}) to (\d{2})/(\d{2})(\d{2}) ([A-Z]{3}) (\d{2})")
# Near-pad closure areas are not downrange hazard areas; ignore vertices this close.
MIN_DOWNRANGE_M = 30000
# Narrowest common bearing range accepted across hazard areas. Areas whose shared
# range is narrower (or empty) do not line up along one departure direction.
MIN_CONSISTENT_DEG = 15
# A wider common range is not a usable departure direction (one broad area).
MAX_CONSISTENT_DEG = 90
# Explicit name normalization only. Vehicle/agency prefixes are dropped because SOLAR
# and the schedule provider place them inconsistently; this never implies a direction.
PREFIXES = (
    r"op x\d+",
    r"space ?x",
    r"nasa",
    r"ula",
    r"falcon (?:9|heavy)",
    r"vulcan(?: vc\w+)?",
    r"atlas v(?: \d+)?",
    r"new glenn",
    r"sls",
    r"blue origin",
)


def mission_keys(name: str) -> set[str]:
    """Normalized identity keys for exact matching, including an LL2 parenthetical alias."""
    name = name.split(" | ")[-1].lower().strip()
    variants = {name}
    designators = {m.strip() for m in re.findall(r"\(([^)]+)\)", name) if re.search(r"\d", m)}
    # "Amazon Leo (KA-06)": the numbered designator identifies the flight; the bare
    # series name would match other flights. "Bandwagon 5 (Dedicated ...)": the
    # parenthetical is descriptive, so the bare name is the identity.
    variants |= designators or {re.sub(r"\([^)]*\)", "", name).strip()}
    keys = set()
    for value in variants:
        for prefix in PREFIXES:
            value = re.sub(r"^" + prefix + r"\b\s*", "", value)
        value = re.sub(r"\bstarlink (?:group )?g?(\d+-\d+)", r"starlink \1", value)
        value = re.sub(r"^(?:dragon )?crs-2 spx-(\d+)", r"crs-\1", value)  # SpaceX CRS-2 numbering
        value = re.sub(r"\s+(?:launch operations?|launch)$", "", value)
        # Keep a separator between digit groups: "11-1" and "1-11" must stay distinct.
        key = re.sub(r"[^a-z0-9.]", "", re.sub(r"(?<=\d)[^a-z0-9]+(?=\d)", ".", value))
        if len(key) >= 3:
            keys.add(key)
    return keys


def parse_time(day: str, hh: str, mm: str, month: str, yy: str) -> datetime:
    return datetime(2000 + int(yy), MONTHS[month], int(day), int(hh), int(mm), tzinfo=timezone.utc)


def parse_windows(text: str) -> tuple[list[dict], int]:
    """Zulu activation windows; inconsistent source entries are counted, not repaired."""
    windows, invalid = [], 0
    for m in WINDOW.finditer(text):
        try:
            start, end = parse_time(*m.groups()[:5]), parse_time(*m.groups()[5:])
        except (KeyError, ValueError):
            invalid += 1
            continue
        if end <= start:
            invalid += 1
            continue
        windows.append({"start": start.isoformat().replace("+00:00", "Z"), "end": end.isoformat().replace("+00:00", "Z")})
    return windows, invalid


def parse_solar(text: str) -> list[dict]:
    """Group launch-hazard features into notices; reject unexpected formats."""
    match = re.fullmatch(r"\s*var\s+\w+\s*=\s*(\{.*\})\s*;?\s*", text, re.S)
    if not match:
        raise ValueError("UNSUPPORTED_SOLAR_FORMAT")
    data = json.loads(match.group(1))
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise ValueError("UNSUPPORTED_SOLAR_FORMAT")
    notices: dict[tuple[str, str], dict] = {}
    for feature in data["features"]:
        props = feature.get("properties") or {}
        msg_id = (props.get("msg_id") or "").strip()
        geometry = feature.get("geometry") or {}
        # Suffixed IDs (_rna, _sec, _spaceSec) are near-pad closures, not downrange hazards.
        if not msg_id or "_" in msg_id or geometry.get("type") != "MultiPolygon":
            continue
        mission = (props.get("mission") or "").strip()
        if not mission:
            continue
        notice = notices.setdefault(
            (msg_id, mission.lower()),
            {
                "msg_id": msg_id,
                "mission": mission,
                "dtg": props.get("dtg"),
                "location": (props.get("location") or "").strip(),
                "windows": [],
                "invalid_windows": 0,
                "invalid_polygons": 0,
                "polygons": [],
            },
        )
        windows, invalid = parse_windows(re.sub(r"<[^>]+>", " ", props.get("popupContent") or ""))
        notice["invalid_windows"] += invalid
        for window in windows:
            if window not in notice["windows"]:
                notice["windows"].append(window)
        for polygon in geometry.get("coordinates") or []:
            try:
                ring = [[round(float(lon), 5), round(float(lat), 5)] for lon, lat in polygon[0]]
                valid = len(ring) >= 3 and all(-90 <= lat <= 90 and -180 <= lon <= 180 for lon, lat in ring)
            except (TypeError, ValueError, IndexError):
                valid = False
            if valid:
                notice["polygons"].append(ring)
            else:
                notice["invalid_polygons"] += 1
    if not notices:
        raise ValueError("UNSUPPORTED_SOLAR_FORMAT")
    # The source occasionally reuses one message ID for different missions; such
    # notices cannot be attributed reliably and are kept only as conflicts.
    ids: dict[str, int] = {}
    for msg_id, _ in notices:
        ids[msg_id] = ids.get(msg_id, 0) + 1
    return [{**n, "id_conflict": ids[n["msg_id"]] > 1} for n in notices.values()]


def east_coast(notice: dict) -> bool:
    if "CAPE CANAVERAL" in notice["location"].upper():
        return True
    return any(27 <= lat <= 33 and -81.5 <= lon <= -70 for ring in notice["polygons"] for lon, lat in ring[:1])


def covers(notice: dict, launch: dict) -> bool | None:
    """Whether the notice windows cover the schedule's launch date; None when undated."""
    if launch["time_precision"] in ("exact", "window") and launch.get("net"):
        at = datetime.fromisoformat(launch["net"].replace("Z", "+00:00"))
    elif launch["time_precision"] == "date" and launch.get("date_label"):
        at = datetime.fromisoformat(launch["date_label"] + "T12:00:00+00:00")
    else:
        return None
    if not notice["windows"]:
        return False
    first = min(datetime.fromisoformat(w["start"].replace("Z", "+00:00")) for w in notice["windows"])
    last = max(datetime.fromisoformat(w["end"].replace("Z", "+00:00")) for w in notice["windows"])
    return first - timedelta(days=1) <= at <= last + timedelta(days=1)


def dtg_key(notice: dict) -> str:
    m = re.fullmatch(r"(\d{2})(\d{4})Z ([A-Z]{3}) (\d{2})", notice.get("dtg") or "")
    return f"{m[4]}{MONTHS.get(m[3], 0):02d}{m[1]}{m[2]}" if m else ""


def associate(notices: list[dict], launch: dict) -> tuple[str, dict | None, str]:
    """Exact-name association, checked against launch timing; never fuzzy."""
    keys = mission_keys(launch["name"])
    named = [n for n in notices if east_coast(n) and mission_keys(n["mission"]) & keys]
    if not named:
        return "not_found", None, "No SOLAR launch hazard notice names this mission."
    coverage = [(n, covers(n, launch)) for n in named]
    dated = [n for n, ok in coverage if ok]
    if any(ok is False for _, ok in coverage) and not dated:
        return "not_found", None, "SOLAR notices for this mission name do not cover the current launch date (earlier attempt or outdated notice)."
    candidates = dated or named
    latest = max(dtg_key(n) for n in candidates)
    newest = [n for n in candidates if dtg_key(n) == latest]
    if len(newest) != 1 or newest[0]["id_conflict"] or newest[0]["invalid_polygons"] or not newest[0]["polygons"]:
        return "ambiguous", None, "Several SOLAR notices, a reused message ID or invalid coordinates match this mission; no hazard area assigned."
    note = "" if dated else " The launch date is not confirmed, so the notice's dates could not be checked against it."
    return "found", newest[0], "Published launch hazard notice " + newest[0]["msg_id"] + " names this mission." + note


def _degrees(sector: dict) -> set[int]:
    if sector["end_deg"] - sector["start_deg"] >= 360:
        return set(range(360))
    start, end = int(sector["start_deg"]) % 360, int(sector["end_deg"]) % 360
    return {d % 360 for d in range(start, start + (end - start) % 360 + 1)}


def consistent_sector(sectors: list[dict]) -> dict | None:
    """Bearings that point toward every downrange hazard area at once.

    A straight ascent passes over each of its downrange areas, so its heading lies in
    the intersection of the areas' bearing sectors. The intersection stays a sector
    (at least 15 degrees, from outward rounding), never a centerline. Areas that share
    no common bearing (alternate, recovery or dogleg areas), or a common range wider
    than 90 degrees, yield None.
    """
    if not sectors:
        return None
    common = set.intersection(*map(_degrees, sectors))
    if not MIN_CONSISTENT_DEG <= len(common) - 1 <= MAX_CONSISTENT_DEG:
        return None
    sector = bearing_sector(list(common))
    if sector is None:
        return None
    return {"start_deg": sector["start_deg"], "end_deg": sector["end_deg"] % 360}


def hazard_evidence(notice: dict, launch: dict) -> dict:
    pad = launch["pad_point"]
    bearings, distances, areas = [], [], []
    for ring in notice["polygons"]:
        ring_bearings, ring_distances = [], []
        for lon, lat in ring:
            inverse = Geodesic.WGS84.Inverse(pad["latitude_deg"], pad["longitude_deg"], lat, lon)
            if inverse["s12"] >= MIN_DOWNRANGE_M:
                ring_bearings.append(inverse["azi1"] % 360)
                ring_distances.append(inverse["s12"])
        if ring_bearings:
            bearings += ring_bearings
            distances += ring_distances
            areas.append(
                {
                    "vertices": len(ring),
                    "nearest_km": round(min(ring_distances) / 1000),
                    "farthest_km": round(max(ring_distances) / 1000),
                    "bearing_sector_deg": bearing_sector(ring_bearings),
                }
            )
    if not bearings:
        raise ValueError("NO_DOWNRANGE_HAZARD_AREA")
    sector = bearing_sector(bearings)
    return {
        "evidence_type": "hazard_corridor",
        "source_name": SOURCE_NAME,
        "parser_version": VERSION,
        "message_id": notice["msg_id"],
        "source_mission_name": notice["mission"],
        "hazard_windows": notice["windows"][:20],
        "hazard_bearing_sector_deg": sector,
        "hazard_consistent_sector_deg": consistent_sector([a["bearing_sector_deg"] for a in areas]),
        "hazard_distance_km": {"min": round(min(distances) / 1000), "max": round(max(distances) / 1000)},
        "hazard_areas": areas,
        "trajectory_available": False,
        "license_note": TERMS_NOTE,
        "chart_url": CHART_URL,
        "note": "Launch hazard areas are safety zones for falling stages and debris. They show the general downrange region, not the flight path, altitude or timing.",
    }
