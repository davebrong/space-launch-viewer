import base64
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update, func
from sqlalchemy.exc import DBAPIError

from services.api import db
from services.api.adapters.ll2 import normalize
from services.api.assessment import calculate
from services.api.assessment import current_versions
from services.api.registry import import_document
from packages.visibility.ensemble import reconstruct
from packages.visibility.common import stamp
from tests.application import support as s


def test_live_provider_enum_regression():
    raw = json.load(open(s.ROOT / "tests/fixtures/raw/ll2.json"))["results"][0]
    raw["pad"].update(latitude=28.608, longitude=-80.604, location={"id": 12})
    raw["status"]["id"] = 9
    raw["net_precision"]["id"] = 5
    doc = normalize(raw, s.provenance())
    assert doc["status"] == "completed" and doc["time_precision"] == "date"
    raw["status"]["id"] = 6
    assert normalize(raw, s.provenance())["status"] == "in_flight"
    raw["net_precision"]["id"] = 3
    assert normalize(raw, s.provenance())["time_precision"] != "date"


def test_immutable_registry_supersession():
    rows = [{"id": "a", "family": "same", "revision": 1}, {"id": "b", "family": "same", "revision": 1}]
    assert len(current_versions(rows, ("family",))) == 2
    rows.append({"id": "c", "family": "same", "revision": 2, "admission": "rejected"})
    assert [r["id"] for r in current_versions(rows, ("family",))] == ["c"]


def test_first_burn_and_gap_admission():
    with s.isolated_database():
        launch = s.launch()
        profile, route = s.profile(launch), s.route(launch)
    profile["powered_intervals"].append({**profile["powered_intervals"][0], "start_s": 600, "end_s": 700})
    rows = reconstruct(profile, route)
    assert len([r for r in rows if r["stage"] == 1]) == 181
    profile["samples"] = [s for s in profile["samples"] if not 50 < s["t_s"] < 80]
    rows = reconstruct(profile, route)
    assert not any(50 < r["t_s"] < 80 for r in rows)
    assert rows[10]["segment_id"] != rows[11]["segment_id"]


def test_complete_negative_requires_complete_fresh_weather():
    at = datetime.now(timezone.utc)
    with s.isolated_database():
        c = s.client()
        loc = s.location(c)
        launch = s.launch(at)
    route, profile = s.route(launch, loc, at), s.profile(launch)
    for sample in profile["samples"]:
        sample["altitude_m"] = 0
        sample["downrange_m"] = sample["t_s"] * 10
    weather = [
        {
            "start": launch["net"],
            "end": stamp(at + timedelta(days=2, hours=1)),
            "total": 10,
            "provenance": [s.provenance(at)],
        }
    ]
    result = calculate(launch, loc, [route], [profile], weather, at)
    assert result["advice"] == "Unlikely" and not result["supported_intervals"]
    assert (
        calculate(launch, loc, [route], [profile], weather, at, source_available=False)["advice"]
        == "Not enough data"
    )
    failed_weather = copy.deepcopy(weather)
    failed_weather[0]["missing_flags"] = ["provider_refresh_failed"]
    assert calculate(launch, loc, [route], [profile], failed_weather, at)["advice"] == "Not enough data"
    assert calculate(launch, loc, [route], [profile], [], at)["advice"] == "Not enough data"
    profile["samples"] = [s for s in profile["samples"] if not 50 < s["t_s"] < 80]
    assert calculate(launch, loc, [route], [profile], weather, at)["advice"] == "Not enough data"


def test_audited_registry_rejects_synthetic_and_hash_mismatch():
    at = datetime.now(timezone.utc)
    with s.isolated_database():
        launch = s.launch(at)
        route = s.route(launch, at=at)
        raw = b"TEST ONLY reviewed source fixture"
        body = {
            "kind": "route-evidence",
            "document": route,
            "raw_base64": base64.b64encode(raw).decode(),
            "review_notes": "TEST ONLY source permission and exact identity review",
        }
        with db.engine().begin() as conn:
            with pytest.raises(ValueError):
                import_document(conn, body, at)
            route["provenance"][0].update(kind="published_path", sha256=hashlib.sha256(raw).hexdigest())
            wrong = copy.deepcopy(body)
            wrong["raw_base64"] = base64.b64encode(b"wrong").decode()
            with pytest.raises(ValueError):
                import_document(conn, wrong, at)
            result = import_document(conn, body, at)
            assert result["id"] == route["id"]
            assert conn.scalar(select(func.count()).select_from(db.audit)) == 1
        with pytest.raises(DBAPIError):
            with db.engine().begin() as conn:
                conn.execute(update(db.routes).values(body={}))


def test_privacy_removes_raw_point_snapshot():
    from services.worker.ingestion import atomic_snapshot
    from pathlib import Path

    at = datetime.now(timezone.utc)
    with s.isolated_database():
        c = s.client()
        loc = s.location(c)
        coord = f"{loc['point']['latitude_deg']:.4f},{loc['point']['longitude_deg']:.4f}"
        sha, path = atomic_snapshot(json.dumps({"TEST ONLY": loc["id"], "point": loc["point"]}).encode())
        with db.engine().begin() as conn:
            conn.execute(
                db.snapshots.insert().values(
                    id=sha,
                    sha256=sha,
                    revision=1,
                    body={"source_url": "https://api.weather.gov/points/" + coord, "path": path},
                    created_at=at,
                )
            )
        assert c.delete("/api/v1/privacy").status_code == 204
        with db.engine().connect() as conn:
            assert conn.scalar(select(func.count()).select_from(db.snapshots)) == 0
        assert not Path(path).exists()


def test_mutations_accept_each_configured_origin(monkeypatch):
    from services.api import main

    tunnel = "http://localhost:13080"
    monkeypatch.setattr(main, "ORIGINS", (s.ORIGIN, tunnel))
    with s.isolated_database():
        c = s.client()
        assert c.post("/api/v1/session", headers={"Origin": tunnel}).status_code == 204
        assert c.post("/api/v1/session", headers={"Origin": "https://evil.example"}).status_code == 403
