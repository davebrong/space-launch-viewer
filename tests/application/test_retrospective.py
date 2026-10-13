from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import update, select

from packages.visibility.common import stamp
from services.api import db
from services.api.pilot import coverage
from tests.application import support as s


def test_retrospective_report_keeps_real_viewing_time_and_excludes_pilot():
    with s.isolated_database(), patch("services.api.main.now", return_value=s.AT):
        c = s.client()
        loc = s.location(c, "md-zip")
        launch = s.launch()
        launch.update(net=stamp(s.AT - timedelta(hours=1)), status="completed")
        with db.engine().begin() as conn:
            conn.execute(
                update(db.launches)
                .where(db.launches.c.id == launch["id"])
                .values(body=launch, status="completed")
            )
        forecast = c.post(
            "/api/v1/assessments", json={"launch_id": launch["id"], "location_id": loc["id"]}
        ).json()
        report = {
            "assessment_id": forecast["id"],
            "outcome": "seen",
            "observed_at": stamp(s.AT - timedelta(minutes=50)),
            "actual_cloud_notes": "Synthetic clouds",
            "notes": "Synthetic sighting only",
            "consent_to_archive": True,
        }
        assert c.post("/api/v1/observations", json=report).status_code == 422
        response = c.post("/api/v1/observations", json={**report, "retrospective": True})
        assert response.status_code == 201, response.text
        assert response.json()["observed_at"] == report["observed_at"]
        assert response.json()["retrospective"] is True
        # Reporting now cannot turn an assessment generated after liftoff into a forecast.
        response = c.post("/api/v1/observations", json={**report, "observed_at": stamp(s.AT)})
        assert response.status_code == 201 and response.json()["retrospective"] is True
        assert (
            c.post(
                "/api/v1/observations",
                json={**report, "retrospective": True, "observed_at": stamp(s.AT + timedelta(hours=1))},
            ).status_code
            == 422
        )
        with db.engine().connect() as conn:
            result = coverage(conn)
        assert result["labeled_denominator"] == 0
        assert result["retrospective_reports"] == 2
        assert result["missed_sighting_attempts"] == 0


def test_prospective_forecast_stays_eligible_for_pilot():
    with s.isolated_database(), patch("services.api.main.now", return_value=s.AT):
        c = s.client()
        loc = s.location(c)
        launch = s.launch()
        forecast = c.post(
            "/api/v1/assessments", json={"launch_id": launch["id"], "location_id": loc["id"]}
        ).json()
        observed = s.AT + timedelta(days=2, minutes=5)
        with patch("services.api.main.now", return_value=observed):
            response = c.post(
                "/api/v1/observations",
                json={
                    "assessment_id": forecast["id"],
                    "outcome": "seen",
                    "observed_at": stamp(observed),
                    "actual_cloud_notes": "Synthetic clouds",
                    "notes": "Synthetic only",
                    "consent_to_archive": True,
                },
            )
        assert response.status_code == 201, response.text
        assert response.json()["retrospective"] is False
        with db.engine().connect() as conn:
            result = coverage(conn)
        assert result["labeled_denominator"] == 1 and result["retrospective_reports"] == 0


def test_deletion_preserves_weather_lookup_shared_by_another_owner():
    with s.isolated_database():
        first, second = s.client(), s.client()
        a, b = s.location(first, "md-zip"), s.location(second, "md-zip")
        p = a["point"]
        key = f"point:{p['latitude_deg']:.4f},{p['longitude_deg']:.4f}"
        with db.engine().begin() as conn:
            conn.execute(db.cache.insert().values(key=key, body={"payload": {"properties": {}}}, failures=0))
        assert first.delete("/api/v1/privacy").status_code == 204
        with db.engine().connect() as conn:
            assert conn.scalar(select(db.cache.c.key).where(db.cache.c.key == key)) == key
        assert second.get("/api/v1/locations/" + b["id"]).status_code == 200
        assert second.delete("/api/v1/locations/" + b["id"]).status_code == 204
        with db.engine().connect() as conn:
            assert conn.scalar(select(db.cache.c.key).where(db.cache.c.key == key)) is None
