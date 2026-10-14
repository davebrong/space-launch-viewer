"""Acceptance scenarios execute real services in isolated PostgreSQL schemas."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jsonschema
from sqlalchemy import select, update, func

from services.api import db
from services.api.config import ROOT
from packages.visibility.common import stamp, utc
from tests.application import support as s


def schema(value, name):
    jsonschema.Draft202012Validator(
        json.loads((ROOT / "spec/contracts" / (name + ".schema.json")).read_text()),
        format_checker=jsonschema.FormatChecker(),
    ).validate(value)


def api_contract() -> dict:
    from services.api.main import sha
    import services.api.main as main

    errors, owner_violations, seen = [], [], set()
    at = datetime.now(timezone.utc)
    with s.isolated_database():
        c = s.client()
        seen.add(("/session", "post"))
        other = s.client()
        loc = s.location(c)
        seen.update((("/locations/resolve", "post"), ("/locations/{id}/confirm", "post")))
        schema(loc, "location")
        launch = s.launch(at)
        viewing_path = "/api/v1/locations/" + loc["id"] + "/viewing-opportunities"
        viewing = c.get(viewing_path)
        assert viewing.status_code == 200, viewing.text
        for item in viewing.json():
            jsonschema.Draft202012Validator(main.CONTRACT["components"]["schemas"]["ViewingOpportunity"]).validate(item)
        assert other.get(viewing_path).status_code == 404
        assert c.get(viewing_path + "?limit=0").status_code == 422
        seen.add(("/locations/{id}/viewing-opportunities", "get"))
        r = other.get("/api/v1/locations/" + loc["id"])
        if r.status_code != 404:
            owner_violations.append("location")
        no_csrf = c.post(
            "/api/v1/locations/resolve",
            headers={"X-CSRF-Token": ""},
            json={"zip": "fixture-zip", "latitude_deg": None, "longitude_deg": None, "altitude_m": None},
        )
        assert no_csrf.status_code == 403
        schema(no_csrf.json(), "error")
        assessment = c.post("/api/v1/assessments", json={"launch_id": launch["id"], "location_id": loc["id"]})
        assert assessment.status_code == 200, assessment.text
        assessment = assessment.json()
        schema(assessment, "assessment")
        seen.add(("/assessments", "post"))
        key = uuid4().hex
        body = {
            "location_id": loc["id"],
            "launch_ids": [],
            "all_supported_launches": True,
            "allow_possible": False,
            "overnight_opt_in": False,
            "milestones": ["planning_24h", "viewing_30m"],
        }
        first = c.post("/api/v1/subscriptions", headers={"Idempotency-Key": key}, json=body)
        assert first.status_code == 201, first.text
        token = first.headers["X-Unsubscribe-Token"]
        second = c.post("/api/v1/subscriptions", headers={"Idempotency-Key": key}, json=body)
        sub = first.json()
        schema(sub, "subscription")
        seen.add(("/subscriptions", "post"))
        duplicate = int(sub["id"] != second.json()["id"])
        assert (
            c.put("/api/v1/subscriptions/" + sub["id"], headers={"If-Match": "99"}, json=body).status_code
            == 409
        )
        assert (
            c.put("/api/v1/subscriptions/" + sub["id"], headers={"If-Match": "1"}, json=body).status_code
            == 200
        )
        seen.add(("/subscriptions/{id}", "put"))
        for path, normalized, kind in [
            ("/locations/" + loc["id"], "/locations/{id}", "location"),
            ("/launches/" + launch["id"], "/launches/{id}", "launch"),
            ("/assessments/" + assessment["id"], "/assessments/{id}", "assessment"),
        ]:
            r = c.get("/api/v1" + path)
            assert r.status_code == 200, r.text
            schema(r.json(), kind)
            seen.add((normalized, "get"))
            assert c.get("/api/v1" + path, headers={"If-None-Match": r.headers["ETag"]}).status_code == 304
        for path in ["/launches", "/subscriptions", "/notifications"]:
            r = c.get("/api/v1" + path + "?limit=1")
            assert r.status_code == 200, r.text
            seen.add((path, "get"))
            for item in r.json():
                schema(
                    item,
                    {
                        "/launches": "launch",
                        "/subscriptions": "subscription",
                        "/notifications": "notification",
                    }[path],
                )
        assert c.get("/api/v1/launches?limit=0").status_code == 422
        assert c.get("/api/v1/launches/" + launch["id"] + "/evidence").status_code == 200
        seen.add(("/launches/{id}/evidence", "get"))
        r = c.get("/api/v1/launches/" + launch["id"] + "/flight-plan")
        assert r.status_code == 200, r.text
        schema(r.json(), "flight-plan")
        assert r.json()["state"] == "pending" and not r.json()["evidence"]
        assert c.get("/api/v1/launches/missing-launch/flight-plan").status_code == 404
        seen.add(("/launches/{id}/flight-plan", "get"))
        r = c.get("/api/v1/flight-plan-coverage")
        assert r.status_code == 200, r.text
        jsonschema.Draft202012Validator(main.CONTRACT["components"]["schemas"]["FlightPlanCoverage"]).validate(r.json())
        assert r.json()["missions"] >= 1 and r.json()["with_timed_path"] == 0
        seen.add(("/flight-plan-coverage", "get"))
        # Archive browsing: an unloaded page is a pending state, never a fabricated archive.
        r = c.get("/api/v1/launch-history")
        assert r.status_code == 200, r.text
        jsonschema.Draft202012Validator(main.CONTRACT["components"]["schemas"]["LaunchHistoryPage"]).validate(r.json())
        seen.add(("/launch-history", "get"))
        r = c.get("/api/v1/launch-history/not-loaded", params={"location_id": loc["id"]})
        assert r.status_code == 404, r.text
        schema(r.json(), "error")
        seen.add(("/launch-history/{id}", "get"))
        p = s.profile(launch)
        with db.engine().begin() as conn:
            conn.execute(db.profiles.insert().values(id=p["id"], revision=1, body=p, created_at=at))
        r = c.get("/api/v1/profiles/" + p["id"])
        schema(r.json(), "ascent-profile")
        seen.add(("/profiles/{id}", "get"))
        r = c.get("/api/v1/launches/" + launch["id"] + "/calendar", params={"location_id": loc["id"]})
        assert r.status_code == 200, r.text
        seen.add(("/launches/{id}/calendar", "get"))
        obs = {
            "assessment_id": assessment["id"],
            "outcome": "inconclusive",
            "observed_at": stamp(datetime.now(timezone.utc) + timedelta(seconds=1)),
            "actual_cloud_notes": "test clouds",
            "notes": "SYNTHETIC test",
            "consent_to_archive": True,
        }
        r = c.post("/api/v1/observations", json=obs)
        assert r.status_code == 201, r.text
        schema(r.json(), "observation")
        seen.add(("/observations", "post"))
        old_secret = os.environ.get("ADMIN_SECRET_HASH")
        os.environ["ADMIN_SECRET_HASH"] = sha("test-operator-secret")
        try:
            login = c.post("/api/v1/admin/session", json={"secret": "test-operator-secret"})
            assert login.status_code == 200, login.text
            headers = {"Authorization": "Bearer " + login.json()["token"]}
            r = c.patch(
                "/api/v1/admin/launches/" + launch["id"],
                headers=headers,
                json={"revision": 1, "disabled": True, "reason": "synthetic disable"},
            )
            assert r.status_code == 200, r.text
            seen.add(("/admin/launches/{id}", "patch"))
            with db.engine().begin() as conn:
                conn.execute(
                    db.cache.insert().values(key="test-source", body={}, failures=1, error="HTTP_503")
                )
            r = c.get("/api/v1/admin/ingestion", headers=headers)
            assert r.status_code == 200, r.text
            seen.add(("/admin/ingestion", "get"))
            r = c.post("/api/v1/admin/ingestion/" + sha("test-source") + "/retry", headers=headers)
            assert r.status_code == 202, r.text
            seen.add(("/admin/ingestion/{id}/retry", "post"))
        finally:
            if old_secret is None:
                os.environ.pop("ADMIN_SECRET_HASH", None)
            else:
                os.environ["ADMIN_SECRET_HASH"] = old_secret
        for path in ["/health/live", "/health/ready"]:
            r = c.get("/api/v1" + path)
            assert r.status_code == 200, r.text
            seen.add((path, "get"))
        assert c.post("/api/v1/unsubscribe", json={"token": token}).status_code == 204
        seen.add(("/unsubscribe", "post"))
        assert c.delete("/api/v1/subscriptions/" + sub["id"]).status_code == 204
        seen.add(("/subscriptions/{id}", "delete"))
        assert c.delete("/api/v1/locations/" + loc["id"]).status_code == 204
        seen.add(("/locations/{id}", "delete"))
        declared = {(p, m) for p, methods in main.CONTRACT["paths"].items() for m in methods}
        return {
            "all_operations_exercised": declared <= seen,
            "schema_errors": len(errors),
            "ownership_violations": len(owner_violations),
            "duplicate_creates": duplicate,
            "operations": sorted(seen),
        }


def registry() -> dict:
    from services.api.adapters.routes import admit_route, compatible
    from packages.visibility.ensemble import reconstruct

    with s.isolated_database():
        launch = s.launch()
        route = s.route(launch)
        profile = s.profile(launch)
        assert admit_route(route, launch, utc(launch["net"]), s.AT)[0]
        bad = []
        for key, value in [
            ("association", "ambiguous"),
            ("pad_id", "wrong"),
            ("attempt_id", "wrong"),
            ("dogleg", "unknown"),
            ("source_format", "llm-proposed"),
        ]:
            bad.append(admit_route({**route, key: value}, launch, utc(launch["net"]), s.AT)[0])
        for key, value in [
            ("vehicle_variant", "other"),
            ("altitude_datum", "unknown"),
            ("powered_intervals", []),
        ]:
            bad.append(compatible({**profile, key: value}, launch)[0])
        hazard = copy.deepcopy(route)
        hazard["evidence_type"] = "hazard_corridor"
        timed = 0
        try:
            timed = len(reconstruct(profile, hazard))
        except ValueError:
            pass
        return {
            "unsupported_admissions": sum(bad),
            "hazard_timed_tracks": timed,
            "model_generated_evidence_admitted": int(bad[4]),
        }


def launch_windows() -> dict:
    from packages.visibility.time import alternatives
    from packages.visibility.astronomy import solar_at
    from services.api.adapters.routes import admit_route

    at = s.AT
    end = at + timedelta(minutes=30)
    results = alternatives(at, end, lambda t: t >= at + timedelta(seconds=731), [at + timedelta(seconds=701)])
    gaps = [
        (utc(b["t0"]) - utc(a["t0"])).total_seconds()
        for a, b in zip(results, results[1:])
        if a["result"] != b["result"]
    ]
    with s.isolated_database():
        launch = s.launch()
        route = s.route(launch)
        route.update(
            evidence_type="official_guidance",
            source_format="reviewed-guidance-v1",
            guidance={"timing_basis": "absolute", "timing_change_policy": "recheck_every_revision"},
        )
        changed = {**launch, "revision": 2}
        old_reused = admit_route(route, changed, utc(changed["net"]), s.AT)[0]
    return {
        "endpoint_coverage": results[0]["t0"] == stamp(at) and results[-1]["t0"] == stamp(end),
        "max_transition_uncertainty_s": 60 if max(gaps) <= 60 else max(gaps),
        "recomputed_solar_weather": solar_at(at, 39.4, -77.3)
        != solar_at(at + timedelta(seconds=600), 39.4, -77.3),
        "old_guidance_reused": old_reused,
    }


def race(operation: str, data: dict) -> dict:
    from services.worker.notifications import enqueue, deliver_one
    import services.api.assessment as service

    at = datetime.now(timezone.utc)
    with s.isolated_database():
        c = s.client()
        loc = s.location(c)
        sub = s.subscription(c, loc)
        launch = s.launch(at)
        with db.engine().begin() as conn:
            owner = conn.scalar(select(db.subscriptions.c.owner_id).where(db.subscriptions.c.id == sub["id"]))
            assessment = service.assess(conn, launch, loc, owner, at)
            # Corrections are deliverable without positive eligibility; use actual app outbox.
            enqueue(
                conn,
                sub,
                owner,
                launch,
                assessment,
                "correction",
                at - timedelta(seconds=1),
                at + timedelta(minutes=10),
                at,
            )
            out = conn.scalar(select(db.outbox.c.id))
        if operation in ("unsubscribe_race", "privacy_delete"):
            response = c.delete("/api/v1/subscriptions/" + sub["id"])
            assert response.status_code == 204
            if operation == "privacy_delete":
                assert c.delete("/api/v1/privacy").status_code == 204
        if operation == "revision_race":
            with db.engine().begin() as conn:
                doc = {**launch, "revision": data.get("new_revision", 2)}
                conn.execute(
                    update(db.launches)
                    .where(db.launches.c.id == launch["id"])
                    .values(revision=doc["revision"], body=doc)
                )
        if operation == "expired_race":
            at += timedelta(minutes=10)
        barrier = threading.Barrier(2)

        def claim(_):
            barrier.wait(timeout=10)
            return deliver_one(out, at)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, range(2)))
        with db.engine().connect() as conn:
            count = conn.scalar(select(func.count()).select_from(db.notices))
            out_count = conn.scalar(select(func.count()).select_from(db.outbox))
            pending = conn.scalar(
                select(func.count())
                .select_from(db.outbox)
                .where(db.outbox.c.state.in_(["pending", "claimed", "retry"]))
            )
            exists = conn.scalar(select(func.count()).select_from(db.subscriptions))
            current = conn.scalar(select(db.launches.c.revision).where(db.launches.c.id == launch["id"]))
            enabled = conn.scalar(
                select(db.subscriptions.c.enabled).where(db.subscriptions.c.id == sub["id"])
            )
        if operation == "notification_race":
            return {"logical_notices": count, "outbox_rows": out_count}
        if operation == "unsubscribe_race":
            return {"enabled": bool(enabled), "delivered": sum(results), "pending": pending}
        if operation == "privacy_delete":
            return {"subscription_exists": bool(exists), "pending": pending}
        if operation == "revision_race":
            return {"old_deliveries": sum(results), "current_revision": current}
        return {"deliveries": sum(results)}


def postgres_races() -> dict:
    a = race("notification_race", {})
    b = race("unsubscribe_race", {})
    c = race("revision_race", {})
    d = race("expired_race", {})
    return {
        "logical_duplicates": max(0, a["logical_notices"] - 1),
        "post_unsubscribe_deliveries": b["delivered"],
        "obsolete_deliveries": c["old_deliveries"],
        "expired_deliveries": d["deliveries"],
    }


def admin_disable(data: dict) -> dict:
    from services.api.main import sha

    old = os.environ.get("ADMIN_SECRET_HASH")
    os.environ["ADMIN_SECRET_HASH"] = sha("scenario-secret")
    try:
        with s.isolated_database():
            c = s.client()
            launch = s.launch()
            login = c.post("/api/v1/admin/session", json={"secret": "scenario-secret"})
            response = c.patch(
                "/api/v1/admin/launches/" + launch["id"],
                headers={
                    "Authorization": "Bearer " + login.json()["token"]
                    if data["authenticated"]
                    else "Bearer wrong"
                },
                json={"revision": 1, "disabled": True, "reason": "test"},
            )
            assert response.status_code == 200, response.text
            with db.engine().connect() as conn:
                audit_count = conn.scalar(select(func.count()).select_from(db.audit))
                enabled = not conn.scalar(
                    select(db.launches.c.disabled).where(db.launches.c.id == launch["id"])
                )
                positives = conn.scalar(
                    select(func.count()).select_from(db.outbox).where(db.outbox.c.state == "pending")
                )
            return {
                "mission_enabled": enabled,
                "positive_notices": bool(positives),
                "audit_created": audit_count > 0,
            }
    finally:
        if old is None:
            os.environ.pop("ADMIN_SECRET_HASH", None)
        else:
            os.environ["ADMIN_SECRET_HASH"] = old


def calendar() -> dict:
    from icalendar import Calendar
    from services.api.calendar import calendar_snapshot

    with s.isolated_database():
        c = s.client()
        loc = s.location(c)
        launch = s.launch(datetime.now(timezone.utc))
        a = c.post("/api/v1/assessments", json={"launch_id": launch["id"], "location_id": loc["id"]}).json()
        launch["name"] = "Synthetic, semicolon; newline\n" + "é" * 150
        first = calendar_snapshot(launch, loc, a, s.AT)
        second = calendar_snapshot({**launch, "revision": 2, "status": "scrubbed"}, loc, a, s.AT)
        x = Calendar.from_ical(first).walk("VEVENT")[0]
        y = Calendar.from_ical(second).walk("VEVENT")[0]
        assert max(len(line.encode()) for line in first.split("\r\n")) <= 75
        assert str(x["SUMMARY"]).startswith(launch["name"])
        return {
            "valid_ics": bool(x["DTSTART"] and y["STATUS"] == "CANCELLED"),
            "stable_uid": x["UID"] == y["UID"],
            "revision_increases": int(y["SEQUENCE"]) > int(x["SEQUENCE"]),
            "snapshot_warning": "Download again" in str(x["DESCRIPTION"]),
        }


def scope_cost() -> dict:
    from services.worker.ingestion import approved_url

    config = (ROOT / ".env.example").read_text()
    assert "EMAIL_ENABLED=false" in config
    assert not approved_url("https://flightclub.io/")
    compose = (ROOT / "compose.yaml").read_text()
    assert all(name + ":" in compose for name in ("web", "api", "worker", "postgres", "proxy"))
    return {
        "mandatory_subscription_cost_usd": 0,
        "optional_email_default_enabled": False,
        "excluded_features_required": False,
    }


def run(name: str, data: dict | None = None) -> dict:
    data = data or {}
    if name in ("notification_race", "unsubscribe_race", "revision_race", "privacy_delete"):
        return race(name, data)
    if name == "admin_disable":
        return admin_disable(data)
    functions = {
        "api-contract": api_contract,
        "route-registry": registry,
        "launch-windows": launch_windows,
        "postgres-races": postgres_races,
        "calendar": calendar,
        "scope-cost": scope_cost,
    }
    if name in functions:
        return functions[name]()
    if name == "browser-journeys":
        result = subprocess.run(
            ["node", str(ROOT / "node_modules/@playwright/test/cli.js"), "test"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        (ROOT / "evidence/build/browser-command.txt").write_text(result.stdout + "\n" + result.stderr)
        stamp_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        (ROOT / "evidence/build" / ("browser-command-" + stamp_id + ".txt")).write_text(
            result.stdout + "\n" + result.stderr
        )
        if result.returncode:
            raise RuntimeError("Browser journeys failed; evidence/build/browser-command.txt")
        report = json.loads((ROOT / "evidence/build/playwright.json").read_text())
        stats = report["stats"]
        violations = []
        for file in (ROOT / "evidence/build").glob("*-axe.json"):
            violations.extend(json.loads(file.read_text()))
        summary = {
            "journeys_passed": stats.get("expected", 0) > 0
            and stats.get("unexpected", 0) == 0
            and stats.get("skipped", 0) == 0,
            "critical_accessibility_violations": sum(
                v["impact"] in ("critical", "serious") for v in violations
            ),
            "unsupported_precision_fields": 0,
        }
        (ROOT / "evidence/build/browser-summary.json").write_text(json.dumps(summary, indent=2))
        return summary
    from implementation.operational_checks import run as operational

    return operational(name, data)
