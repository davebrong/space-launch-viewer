from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

from packages.visibility.common import point, stamp
from packages.visibility.planning import calculate_plan
from services.api.adapters.flight_plans import sector

AT = datetime(2026, 10, 13, 10, 33, 44, tzinfo=timezone.utc)
LAUNCH = {
    "name": "Falcon 9 Block 5 | Dragon CRS-2 SpX-35",
    "vehicle_variant": "Falcon 9 Block 5",
    "mission_class": "Low Earth Orbit",
    "pad_name": "Space Launch Complex 40",
    "pad_point": point(28.562, -80.577),
    "net": stamp(AT),
    "actual_liftoff": None,
    "time_precision": "exact",
    "status": "scheduled",
    "disabled": False,
}
LOCATION = {"point": point(39.294961, -76.622341)}  # ZIP 21201 (Baltimore)


def published(direction: str) -> dict:
    """Synthetic admitted heading record; the direction is a test input, not mission data."""
    return {
        "state": "found",
        "evidence": [
            {
                "evidence_type": "departure_heading",
                "source_name": "Next Spaceflight",
                "source_url": "https://nextspaceflight.com/launches/details/9001/",
                "source_sha256": "c" * 64,
                "fetched_at": stamp(AT - timedelta(days=1)),
                "parser_version": "test",
                "departure_direction": direction,
                "departure_sector_deg": sector(direction),
                "trajectory_available": False,
                "note": "test",
            }
        ],
    }


NORTHEAST = published("northeast")


def test_plan_depends_on_location_and_scheduled_time_not_postlaunch_outcomes():
    plan = calculate_plan(LAUNCH, LOCATION, [], AT - timedelta(hours=1), NORTHEAST)
    assert plan and plan["watch_interval"] and plan["directions"] == ["south", "southeast", "east"]
    # One envelope row per modeled heading that rises into view.
    assert 1 <= len(plan["windows"]) <= 5
    assert max(w["max_elevation_max_deg"] for w in plan["windows"]) > 5
    completed = {**LAUNCH, "status": "completed", "actual_liftoff": stamp(AT + timedelta(hours=2))}
    assert calculate_plan(completed, LOCATION, [], AT + timedelta(hours=3), NORTHEAST) == plan
    shifted = calculate_plan({**LAUNCH, "net": stamp(AT + timedelta(hours=1))}, LOCATION, [], AT, NORTHEAST)
    for bound in ("start", "end"):
        before = datetime.fromisoformat(plan["watch_interval"][bound].replace("Z", "+00:00"))
        after = datetime.fromisoformat(shifted["watch_interval"][bound].replace("Z", "+00:00"))
        assert after - before == timedelta(hours=1)
    assert calculate_plan(LAUNCH, {"point": point(-35, 140)}, [], AT, NORTHEAST)["watch_interval"] is None
    json.dumps(plan, allow_nan=False)


def test_postlaunch_forecasts_cannot_leak_into_the_prelaunch_plan():
    row = {
        "start": stamp(AT),
        "end": stamp(AT + timedelta(hours=1)),
        "total": 22,
        "provenance": [
            {"issued_at": stamp(AT - timedelta(hours=1)), "fetched_at": stamp(AT - timedelta(minutes=30))}
        ],
    }
    plan = calculate_plan(LAUNCH, LOCATION, [row], AT + timedelta(hours=2), NORTHEAST)
    assert plan["cloud_cover_min_pct"] == 22
    for field in ("issued_at", "fetched_at"):
        late = deepcopy(row)
        late["provenance"][0][field] = stamp(AT + timedelta(seconds=1))
        later = calculate_plan(LAUNCH, LOCATION, [late], AT + timedelta(hours=2), NORTHEAST)
        assert later["cloud_cover_min_pct"] is None


def test_no_distant_plan_without_published_mission_heading_or_for_stopped_launches():
    # Regression for issue #1: the former Dragon/ISS northeast fallback is gone.
    for override in (
        {},
        {"name": "Starlink", "mission_class": "Low Earth Orbit"},
        {"vehicle_variant": "Vulcan"},
        {"mission_class": "International Space Station"},
        {"time_precision": "unknown"},
        {"time_precision": "window"},
    ):
        assert calculate_plan({**LAUNCH, **override}, LOCATION, [], AT) is None
    for override in ({"disabled": True}, {"status": "scrubbed"}, {"status": "hold"}):
        assert calculate_plan({**LAUNCH, **override}, LOCATION, [], AT, NORTHEAST) is None
