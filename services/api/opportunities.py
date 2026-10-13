"""Location-specific list summaries; absence of a plan is not a negative sighting."""

from __future__ import annotations

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from packages.visibility.common import utc


def within_viewing_horizon(launch: dict, location: dict, now: datetime) -> bool:
    """Today through 30 calendar days ahead in the observer's zone; date-only stays a source date."""
    today = now.astimezone(ZoneInfo(location["timezone"])).date()
    if launch["time_precision"] == "date":
        try:
            day = date.fromisoformat(launch.get("date_label") or "")
        except ValueError:
            return False
        return today <= day <= today + timedelta(days=30)
    if launch["time_precision"] not in ("exact", "window"):
        return False
    zone = ZoneInfo(location["timezone"])
    interval = launch.get("window") if launch["time_precision"] == "window" else None
    if not interval and not launch.get("net"):
        return False
    start = utc(interval["start"] if interval else launch["net"]).astimezone(zone).date()
    end = utc(interval["end"] if interval else launch["net"]).astimezone(zone).date()
    return start <= today + timedelta(days=30) and end >= today


def summarize(launch: dict, assessment: dict | None = None, plan: dict | None = None) -> dict:
    result = {
        "launch_id": launch["id"],
        "viewable": False,
        "label": "No viewing estimate",
        "basis": "unavailable",
        "directions": [],
        "watch_interval": None,
    }
    if launch["disabled"] or launch["status"] in ("hold", "scrubbed", "cancelled"):
        return {
            **result,
            "label": "Launch paused" if launch["status"] == "hold" else "Not an active opportunity",
        }
    plan = assessment.get("planning_scenario") if assessment else plan
    nearby = bool(plan and plan.get("kind") == "near_launch_site")
    if launch["time_precision"] not in ("exact", "window") and not nearby:
        return {**result, "label": "Launch time unconfirmed"}
    if assessment:
        plan = assessment.get("planning_scenario")
        if assessment["weather_state"] == "poor":
            return {**result, "label": "Poor viewing conditions"}
        intervals = assessment.get("supported_intervals", [])
        if assessment["mode"] == "reconstructed":
            intervals = intervals or [w["interval"] for w in assessment["windows"]]
        elif assessment["mode"] == "official_guidance":
            intervals = intervals or assessment.get("official_intervals", [])
        else:
            intervals = []
        if intervals and (assessment["fresh"] or launch["status"] == "completed"):
            return {
                **result,
                "viewable": True,
                "label": "Viewing plan available",
                "basis": assessment["mode"],
                "watch_interval": intervals[0],
            }
    if plan:
        if not plan["watch_interval"] and not nearby:
            return {**result, "label": "Outside simulated viewing area", "basis": "simulation"}
        if plan["cloud_cover_min_pct"] is not None and plan["cloud_cover_min_pct"] >= 75:
            return {**result, "label": "Poor viewing conditions", "basis": "simulation"}
        return {
            **result,
            "viewable": True,
            "label": "Nearby launch estimate" if nearby else "Simulated viewing plan",
            "basis": "near_launch_site" if nearby else "simulation",
            "directions": plan["directions"],
            "watch_interval": plan["watch_interval"],
        }
    return result
