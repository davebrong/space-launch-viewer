from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from packages.visibility.common import point, stamp, utc

# Source IDs from LL2 location/pad metadata. Geographic post-filter is additional protection.
CAPE_LOCATION_IDS = {12, 27}


def supported_pad(pad: dict) -> bool:
    return (
        pad.get("location", {}).get("id") in CAPE_LOCATION_IDS
        and 28 <= float(pad.get("latitude", 0)) <= 29
        and -81 <= float(pad.get("longitude", 0)) <= -80
    )


def normalize(raw: dict, provenance: dict, previous: dict | None = None) -> dict:
    if not supported_pad(raw["pad"]):
        raise ValueError("unsupported_pad")
    pad, mission = raw["pad"], raw.get("mission") or {}
    status = {
        1: "scheduled",
        2: "unknown",  # Provider says placeholder/rough estimation.
        3: "completed",
        4: "completed",
        5: "hold",
        6: "in_flight",  # Source confirms flight, not an actual liftoff timestamp.
        7: "completed",
        8: "scheduled",
        9: "completed",  # Payload deployed; verified against the provider config endpoint.
    }.get(raw.get("status", {}).get("id"), "unknown")
    net = stamp(utc(raw["net"])) if raw.get("net") else None
    precision_id = (raw.get("net_precision") or {}).get("id")
    window = None
    if (
        raw.get("window_start")
        and raw.get("window_end")
        and utc(raw["window_end"]) > utc(raw["window_start"])
    ):
        window = {"start": stamp(utc(raw["window_start"])), "end": stamp(utc(raw["window_end"]))}
    precision = (
        "exact"
        if precision_id in (0, 1) and net
        else "date"
        if precision_id == 5 and net
        else "window"
        if precision_id in (2, 3, 4) and window
        else "unknown"
    )
    attempt = previous["attempt_id"] if previous else str(uuid5(NAMESPACE_URL, raw["id"] + ":attempt:1"))
    if previous and previous["status"] == "scrubbed" and status == "scheduled":
        attempt = str(uuid5(NAMESPACE_URL, raw["id"] + ":" + str(previous["revision"] + 1)))
    return {
        "schema_version": "1.0",
        "id": raw["id"],
        "revision": previous["revision"] if previous else 1,
        "provider_id": raw["id"],
        "mission_id": str(mission["id"]) if mission.get("id") else None,
        "name": raw["name"],
        "pad_id": str(pad["id"]),
        "pad_name": pad["name"],
        "pad_point": point(float(pad["latitude"]), float(pad["longitude"])),
        "vehicle_variant": raw.get("rocket", {}).get("configuration", {}).get("full_name"),
        "mission_class": (mission.get("orbit") or {}).get("name"),
        "recovery_configuration": None,
        "attempt_id": attempt,
        "time_precision": precision,
        "net": net,
        "window": window,
        "date_label": net[:10] if precision == "date" else None,
        "date_basis_timezone": "UTC" if precision == "date" else None,
        "actual_liftoff": None,
        "status": status,
        "disabled": previous.get("disabled", False) if previous else False,
        "source_updated_at": raw.get("last_updated"),
        "provenance": [provenance],
    }
