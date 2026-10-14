"""Location-specific list summaries; absence of a plan is not a negative sighting."""

from __future__ import annotations

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from packages.visibility.common import utc

# Missing route coverage stays visibly distinct from modeled geometry results.
COVERAGE_LABELS = {
    "pending": "Route check pending",
    "queued": "Route check pending",
    "not_found": "No published route found",
    "unavailable": "Route source unavailable",
    "blocked": "Route source unavailable",
    "ambiguous": "Route source ambiguous",
    "found": "Route information without a viewing model",
    "stale": "Route information without a viewing model",
}
# Undated or far-off missions: route sources publish only a few days before launch.
NOT_YET_LABEL = "Route not published yet"


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


def weather_note(plan: dict) -> str | None:
    if plan.get("cloud_cover_min_pct") is None:
        return None
    low, high = round(plan["cloud_cover_min_pct"]), round(plan["cloud_cover_max_pct"])
    span = f"{low}%" if low == high else f"{low}–{high}%"
    return f"Forecast {span} cloud cover" + (" — clouds may block the view" if low >= 75 else "")


def summarize(
    launch: dict, assessment: dict | None = None, plan: dict | None = None, flight_plan: dict | None = None
) -> dict:
    result = {
        "launch_id": launch["id"],
        "viewable": False,
        "label": "No viewing estimate",
        "basis": "unavailable",
        "directions": [],
        "watch_interval": None,
        "relative_window": None,
        "coverage_state": flight_plan["state"] if flight_plan else None,
        "weather_note": None,
    }
    if launch["disabled"] or launch["status"] in ("hold", "scrubbed", "cancelled"):
        return {
            **result,
            "label": "Launch paused" if launch["status"] == "hold" else "Not an active opportunity",
        }
    plan = assessment.get("planning_scenario") if assessment else plan
    kind = plan.get("kind") if plan else None
    nearby = kind == "near_launch_site"
    heading = kind == "published_heading_model"
    if assessment:
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
    if plan and heading:
        common = {**result, "basis": "published_heading", "weather_note": weather_note(plan)}
        if not plan["relative_window"]:
            label = "Grazes your horizon (modeled)" if plan["horizon_grazing"] else "Below your horizon (modeled)"
            return {**common, "label": label}
        timed = bool(plan["watch_interval"])
        return {
            **common,
            # Clear-sky geometry; an undated launch cannot be placed on the viewing calendar.
            "viewable": timed or launch["time_precision"] == "date",
            "label": "Clear-sky estimate" if timed else "Clear-sky estimate · time TBA",
            "directions": plan["directions"],
            "watch_interval": plan["watch_interval"],
            "relative_window": plan["relative_window"],
        }
    if plan:
        if launch["time_precision"] not in ("exact", "window") and not nearby:
            return {**result, "label": "Launch time unconfirmed"}
        if not plan["watch_interval"] and not nearby:
            return {**result, "label": "Outside simulated viewing area", "basis": "simulation"}
        return {
            **result,
            "viewable": True,
            "label": "Nearby launch estimate" if nearby else "Simulated viewing plan",
            "basis": "near_launch_site" if nearby else "simulation",
            "directions": plan["directions"],
            "watch_interval": plan["watch_interval"],
            "weather_note": weather_note(plan),
        }
    if flight_plan:
        kinds = {e["evidence_type"] for e in flight_plan["evidence"]}
        if flight_plan.get("conflict"):
            label = "Route sources disagree"
        elif kinds == {"hazard_corridor"}:
            label = "Hazard areas only; path unresolved"
        elif flight_plan["state"] == "not_found" and not flight_plan.get("publication_expected", True):
            label = NOT_YET_LABEL
        else:
            label = COVERAGE_LABELS[flight_plan["state"]]
        return {**result, "label": label}
    return result
