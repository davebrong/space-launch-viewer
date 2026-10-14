from datetime import timedelta

from packages.visibility.common import point, stamp
from packages.visibility.planning import calculate_plan
from services.api.opportunities import summarize, within_viewing_horizon
from tests.application.test_planning import LAUNCH, LOCATION, AT


FLORIDA = {"point": point(29.0, -81.0), "timezone": "America/New_York"}
BANDWAGON = {
    **LAUNCH,
    "id": "bandwagon",
    "name": "Falcon 9 | Bandwagon 5",
    "mission_class": "Rideshare",
    "pad_name": "Space Launch Complex 40",
}


def test_nearby_is_location_based_not_dragon_or_zip_based():
    plan = calculate_plan(BANDWAGON, FLORIDA, [], AT)
    assert plan["kind"] == "near_launch_site"
    assert 83000 < plan["pad_distance_m"] < 85000
    assert plan["directions"] == ["southeast"]
    assert plan["windows"] == []
    assert plan["watch_interval"]["start"] == stamp(AT - timedelta(minutes=2))
    assert summarize(BANDWAGON, plan=plan)["viewable"]
    assert calculate_plan(BANDWAGON, LOCATION, [], AT) is None
    south = {"point": point(28.1, -80.6)}
    assert calculate_plan(BANDWAGON, south, [], AT)["directions"] == ["north"]
    for vehicle in ("Vulcan VC6L", "New Glenn", "Falcon 9 Block 5"):
        assert calculate_plan({**BANDWAGON, "vehicle_variant": vehicle}, FLORIDA, [], AT)
    for change in (
        {"status": "hold"},
        {"disabled": True},
        {"pad_name": "Unknown Pad"},
        {"time_precision": "unknown"},
    ):
        assert calculate_plan({**BANDWAGON, **change}, FLORIDA, [], AT) is None


def test_nearby_date_only_keeps_opportunity_without_making_up_time():
    launch = {
        **BANDWAGON,
        "vehicle_variant": "Vulcan VC6L",
        "time_precision": "date",
        "date_label": "2026-10-29",
        "net": "2026-10-29T00:00:00Z",
    }
    plan = calculate_plan(launch, FLORIDA, [], AT)
    assert plan["launch_time"] is None and plan["watch_interval"] is None
    assert summarize(launch, plan=plan)["viewable"]
    assert calculate_plan(launch, LOCATION, [], AT) is None


def test_horizon_local_today_30_days_dst_and_date_only():
    for day, expected in ((-1, False), (0, True), (30, True), (31, False)):
        launch = {**BANDWAGON, "net": stamp(AT + timedelta(days=day))}
        assert within_viewing_horizon(launch, FLORIDA, AT) == expected
    assert within_viewing_horizon({**BANDWAGON, "status": "completed"}, FLORIDA, AT)
    assert not within_viewing_horizon({**BANDWAGON, "net": "2026-10-13T03:59:00Z"}, FLORIDA, AT)
    assert within_viewing_horizon(
        {**BANDWAGON, "time_precision": "date", "date_label": "2026-10-13"}, FLORIDA, AT
    )
    assert not within_viewing_horizon(
        {**BANDWAGON, "time_precision": "date", "date_label": "October 2026"}, FLORIDA, AT
    )
    window = {
        **BANDWAGON,
        "time_precision": "window",
        "net": None,
        "window": {"start": "2026-10-13T03:55:00Z", "end": "2026-10-13T04:05:00Z"},
    }
    assert within_viewing_horizon(window, FLORIDA, AT)
    plan = calculate_plan(window, FLORIDA, [], AT)
    assert plan["watch_interval"] == {"start": "2026-10-13T03:53:00Z", "end": "2026-10-13T04:10:00Z"}


def test_nearby_weather_never_uses_later_or_stale_forecasts():
    row = {
        "start": stamp(AT - timedelta(hours=1)),
        "end": stamp(AT + timedelta(hours=1)),
        "total": 90,
        "provenance": [{"issued_at": stamp(AT), "fetched_at": stamp(AT)}],
    }
    plan = calculate_plan(BANDWAGON, FLORIDA, [row], AT)
    # Clear-sky guidance leads; the cloud forecast is a secondary note, not a gate.
    cloudy = summarize(BANDWAGON, plan=plan)
    assert cloudy["viewable"] and "90" in cloudy["weather_note"]
    for changed in (
        {"missing_flags": ["provider_refresh_failed"]},
        {
            "provenance": [
                {
                    "issued_at": stamp(AT + timedelta(minutes=1)),
                    "fetched_at": stamp(AT + timedelta(minutes=1)),
                }
            ]
        },
        {
            "provenance": [
                {"issued_at": stamp(AT - timedelta(days=1)), "fetched_at": stamp(AT - timedelta(days=1))}
            ]
        },
    ):
        plan = calculate_plan(BANDWAGON, FLORIDA, [{**row, **changed}], AT + timedelta(hours=1))
        assert plan["cloud_cover_min_pct"] is None
