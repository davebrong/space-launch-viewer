"""Synthetic application inputs live only under tests; independent of fixture expected outputs."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient

from services.api import db
from services.api.main import app
from services.api.config import ROOT, ORIGIN
from packages.visibility.common import point, stamp

AT = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)


@contextmanager
def isolated_database():
    original = db.engine
    base = original()
    schema = "test_" + uuid4().hex
    with base.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    test_engine = create_engine(
        os.environ["DATABASE_URL"], connect_args={"options": "-csearch_path=" + schema}, pool_size=25
    )
    db.engine = lambda: test_engine
    try:
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
        yield test_engine
    finally:
        db.engine = original
        test_engine.dispose()
        with base.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def client() -> TestClient:
    c = TestClient(app, base_url=ORIGIN)
    c.headers["Origin"] = ORIGIN
    r = c.post("/api/v1/session")
    assert r.status_code == 204, r.text
    c.headers["X-CSRF-Token"] = r.headers["X-CSRF-Token"]
    return c


def location(c, zip="21201") -> dict:
    r = c.post(
        "/api/v1/locations/resolve",
        json={"zip": zip, "latitude_deg": None, "longitude_deg": None, "altitude_m": None},
    )
    assert r.status_code == 200, r.text
    loc = r.json()
    r = c.post(
        f"/api/v1/locations/{loc['id']}/confirm", json={"revision": loc["revision"], "confirmed": True}
    )
    assert r.status_code == 200, r.text
    return r.json()


def provenance(at=AT) -> dict:
    return {
        "source_url": "https://example.invalid/synthetic-test-only",
        "sha256": "a" * 64,
        "fetched_at": stamp(at),
        "issued_at": stamp(at),
        "source_revision": "synthetic-v1",
        "license": "Synthetic test fixture",
        "parser_version": "test-v1",
        "kind": "synthetic",
        "notes": ["Not a real forecast"],
    }


def launch(at=AT) -> dict:
    id = str(uuid4())
    doc = {
        "schema_version": "1.0",
        "id": id,
        "revision": 1,
        "provider_id": id,
        "mission_id": "synthetic",
        "name": "SYNTHETIC TEST | Cape ascent",
        "pad_id": "80",
        "pad_name": "SYNTHETIC Cape pad",
        "pad_point": point(28.608, -80.604),
        "vehicle_variant": "test-vehicle",
        "mission_class": "test-orbit",
        "recovery_configuration": "test-recovery",
        "attempt_id": str(uuid4()),
        "time_precision": "exact",
        "net": stamp(at + timedelta(days=2)),
        "window": None,
        "date_label": None,
        "date_basis_timezone": None,
        "actual_liftoff": None,
        "status": "scheduled",
        "disabled": False,
        "source_updated_at": stamp(at),
        "provenance": [provenance(at)],
    }
    with db.engine().begin() as conn:
        conn.execute(
            db.launches.insert().values(
                id=id,
                revision=1,
                body=doc,
                created_at=at,
                net=at + timedelta(days=2),
                status="scheduled",
                disabled=False,
            )
        )
        conn.execute(
            db.revisions.insert().values(id=str(uuid4()), revision=1, launch_id=id, body=doc, created_at=at)
        )
    return doc


def route(launch_doc: dict, loc: dict | None = None, at=AT) -> dict:
    return {
        "schema_version": "1.0",
        "id": str(uuid4()),
        "revision": 1,
        "launch_id": launch_doc["id"],
        "attempt_id": launch_doc["attempt_id"],
        "pad_id": launch_doc["pad_id"],
        "mission_aliases": [launch_doc["name"]],
        "evidence_type": "published_path",
        "admission": "approved",
        "association": "exact",
        "valid_interval": {"start": stamp(at - timedelta(days=1)), "end": stamp(at + timedelta(days=4))},
        "reviewed_schedule_revision": launch_doc["revision"],
        "source_format": "reviewed-path-v1",
        "parser_version": "reviewed-v1",
        "dogleg": "absent_supported",
        "path_vertices": [point(28.608, -80.604), point(45, -70)],
        "hazard_polygons": [],
        "heading_range_deg": None,
        "guidance": None,
        "uncertainty_notes": ["SYNTHETIC TEST ONLY"],
        "provenance": [provenance(at)],
    }


def profile(launch_doc: dict) -> dict:
    return {
        "schema_version": "1.0",
        "id": str(uuid4()),
        "revision": 1,
        "historical_mission": "synthetic-training",
        "vehicle_variant": launch_doc["vehicle_variant"],
        "mission_class": launch_doc["mission_class"],
        "recovery_configuration": launch_doc["recovery_configuration"],
        "compatible_pad_ids": [launch_doc["pad_id"]],
        "launch_latitude_deg": 28.608,
        "time_origin": "seconds_since_actual_liftoff",
        "altitude_datum": "WGS84_ELLIPSOID",
        "datum_conversion": None,
        "downrange_definition": "synthetic geodesic meters",
        "stage_identity_notes": "two separate synthetic stages",
        "compatibility": "approved",
        "compatibility_rationale": "synthetic numerical tests only",
        "training_mission_ids": ["synthetic-training"],
        "held_out_mission_ids": ["synthetic-heldout"],
        "samples": [
            {
                "t_s": t,
                "stage": stage,
                "altitude_m": 50000 + t * 250,
                "downrange_m": t * 1500,
                "speed_m_s": None,
            }
            for stage in (1, 2)
            for t in range(0, 901, 5)
        ],
        "powered_intervals": [
            {
                "stage": s,
                "start_s": 0,
                "end_s": 900,
                "source_event_start": "synthetic ignition",
                "source_event_end": "synthetic cutoff",
                "emission": "active_engine",
            }
            for s in (1, 2)
        ],
        "provenance": [provenance()],
    }


def subscription(c, loc) -> dict:
    r = c.post(
        "/api/v1/subscriptions",
        headers={"Idempotency-Key": uuid4().hex},
        json={
            "location_id": loc["id"],
            "launch_ids": [],
            "all_supported_launches": True,
            "allow_possible": True,
            "overnight_opt_in": True,
            "milestones": ["planning_24h", "viewing_30m"],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()
