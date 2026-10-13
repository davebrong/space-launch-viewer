from copy import deepcopy
from unittest.mock import patch

from sqlalchemy import update

from services.api import db
from services.api.opportunities import summarize
from tests.application import support as s
from tests.application.test_planning import LAUNCH, LOCATION, AT
from packages.visibility.planning import calculate_plan


def test_summary_requires_observer_geometry_and_excludes_poor_or_stopped_plans():
    launch = {**LAUNCH, "id": "test"}
    plan = calculate_plan(launch, LOCATION, [], AT)
    assert summarize(launch, plan=plan)["viewable"]
    assert not summarize(launch)["viewable"]
    assert not summarize({**launch, "status": "hold"}, plan=plan)["viewable"]
    assert not summarize(launch, plan={**plan, "watch_interval": None})["viewable"]
    assert not summarize(launch, plan={**plan, "cloud_cover_min_pct": 90})["viewable"]
    assessment = {
        "mode": "official_guidance",
        "fresh": True,
        "weather_state": "clear",
        "official_intervals": [plan["watch_interval"]],
    }
    assert summarize(launch, assessment)["basis"] == "official_guidance"
    assert not summarize(launch, {**assessment, "fresh": False})["viewable"]
    assert not summarize(launch, {**assessment, "weather_state": "poor"})["viewable"]


def test_listing_is_location_specific_paginated_private_and_does_not_guess_rideshare():
    with s.isolated_database(), patch("services.api.main.now", return_value=s.AT):
        client, stranger = s.client(), s.client()
        near = s.location(client, "md-zip")
        launch = s.launch()
        station = {**launch, "name": LAUNCH["name"], "vehicle_variant": "Falcon 9 Block 5"}
        other = s.launch()
        rideshare = {**other, "name": "Falcon 9 | Bandwagon 5", "vehicle_variant": "Falcon 9 Block 5"}
        with db.engine().begin() as conn:
            for row in (station, rideshare):
                conn.execute(update(db.launches).where(db.launches.c.id == row["id"]).values(body=row))
        url = f"/api/v1/locations/{near['id']}/viewing-opportunities"
        result = client.get(url)
        assert result.status_code == 200, result.text
        rows = {r["launch_id"]: r for r in result.json()}
        assert rows[station["id"]]["viewable"]
        assert rows[rideshare["id"]]["label"] == "No viewing estimate"
        florida = s.location(client, "fl-zip")
        florida_url = f"/api/v1/locations/{florida['id']}/viewing-opportunities"
        nearby = {r["launch_id"]: r for r in client.get(florida_url).json()}
        assert nearby[rideshare["id"]]["viewable"]
        assert nearby[rideshare["id"]]["basis"] == "near_launch_site"
        details = client.post(
            "/api/v1/assessments", json={"launch_id": rideshare["id"], "location_id": florida["id"]}
        )
        assert details.status_code == 200, details.text
        assert details.json()["planning_scenario"]["directions"] == ["southeast"]
        # Cached results for the other observer must not acquire the nearby plan.
        again = {r["launch_id"]: r for r in client.get(url).json()}
        assert not again[rideshare["id"]]["viewable"]
        first = client.get(url + "?limit=1")
        assert len(first.json()) == 1
        second = client.get(url + "?limit=1&cursor=" + first.headers["X-Next-Cursor"])
        assert first.json()[0]["launch_id"] != second.json()[0]["launch_id"]
        assert stranger.get(url).status_code == 404
        far = deepcopy(near)
        far["point"].update(latitude_deg=-35, longitude_deg=140)
        with db.engine().begin() as conn:
            conn.execute(update(db.locations).where(db.locations.c.id == near["id"]).values(body=far))
        rows = {r["launch_id"]: r for r in client.get(url).json()}
        assert not rows[station["id"]]["viewable"]
