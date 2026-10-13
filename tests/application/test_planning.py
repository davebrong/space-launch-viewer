from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

from packages.visibility.common import point, stamp
from packages.visibility.planning import calculate_plan

AT = datetime(2026, 10, 13, 10, 33, 44, tzinfo=timezone.utc)
LAUNCH = {
    "name": "Falcon 9 | Dragon CRS-2 SpX-35",
    "vehicle_variant": "Falcon 9 Block 5",
    "mission_class": "Low Earth Orbit",
    "pad_point": point(28.562, -80.577),
    "net": stamp(AT),
    "actual_liftoff": None,
    "time_precision": "exact",
    "status": "scheduled",
    "disabled": False,
}
LOCATION = {"point": point(39.0, -77.0)}


def test_plan_depends_on_location_and_scheduled_time_not_postlaunch_outcomes():
    plan = calculate_plan(LAUNCH, LOCATION, [], AT - timedelta(hours=1))
    assert plan and plan["watch_interval"] and plan["directions"] == ["south", "southeast", "east"]
    assert len(plan["windows"]) == 1
    assert plan["windows"][0]["max_elevation_max_deg"] > 5
    completed = {**LAUNCH, "status": "completed", "actual_liftoff": stamp(AT + timedelta(hours=2))}
    assert calculate_plan(completed, LOCATION, [], AT + timedelta(hours=3)) == plan
    shifted = calculate_plan({**LAUNCH, "net": stamp(AT + timedelta(hours=1))}, LOCATION, [], AT)
    for bound in ("start", "end"):
        before = datetime.fromisoformat(plan["watch_interval"][bound].replace("Z", "+00:00"))
        after = datetime.fromisoformat(shifted["watch_interval"][bound].replace("Z", "+00:00"))
        assert after - before == timedelta(hours=1)
    assert calculate_plan(LAUNCH, {"point": point(-35, 140)}, [], AT)["watch_interval"] is None
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
    plan = calculate_plan(LAUNCH, LOCATION, [row], AT + timedelta(hours=2))
    assert plan["cloud_cover_min_pct"] == 22
    for field in ("issued_at", "fetched_at"):
        late = deepcopy(row)
        late["provenance"][0][field] = stamp(AT + timedelta(seconds=1))
        assert (
            calculate_plan(LAUNCH, LOCATION, [late], AT + timedelta(hours=2))["cloud_cover_min_pct"] is None
        )


def test_no_plan_for_unsupported_family_or_imprecise_or_stopped_launch():
    for override in (
        {"name": "Starlink", "mission_class": "Low Earth Orbit"},
        {"vehicle_variant": "Vulcan"},
        {"time_precision": "unknown"},
        {"time_precision": "window"},
        {"disabled": True},
        {"status": "scrubbed"},
        {"pad_point": point(34.7, -120.6)},
    ):
        assert calculate_plan({**LAUNCH, **override}, LOCATION, [], AT) is None
