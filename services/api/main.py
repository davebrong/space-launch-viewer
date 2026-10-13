from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from uuid import uuid4

import jsonschema
from fastapi import FastAPI, Request, Response, HTTPException, Body, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, update, delete, func, text
from sqlalchemy.exc import SQLAlchemyError

from . import db
from .config import ROOT, ORIGIN
from .adapters.census import resolve_zip, timezone_at
from .assessment import assess, cached_weather
from packages.visibility.common import digest, utc, stamp, point
from packages.visibility.astronomy import model_manifest

app = FastAPI(title="Launch visibility", version="0.1.0", docs_url="/api/docs")
log = logging.getLogger("launch_visibility")
CONTRACT = json.loads((ROOT / "spec/contracts/openapi.json").read_text())


def now() -> datetime:
    return datetime.now(timezone.utc)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def fail(code: str, message: str, status: int = 422) -> None:
    raise HTTPException(status, {"code": code, "message": message})


def validate(name: str, body: dict) -> dict:
    schema = CONTRACT["components"]["schemas"][name]
    try:
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(body)
        json.dumps(body, allow_nan=False)
    except (jsonschema.ValidationError, ValueError):
        fail("INVALID_INPUT", "Input does not match the documented contract")
    return body


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "schema_version": "1.0",
            "id": str(uuid4()),
            "revision": 1,
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", str(uuid4())),
            "retryable": status in (429, 503),
            "retry_after_s": 60 if status in (429, 503) else None,
            "details": [],
        },
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    detail = (
        exc.detail if isinstance(exc.detail, dict) else {"code": "INVALID_INPUT", "message": str(exc.detail)}
    )
    return error_response(request, exc.status_code, detail["code"], detail["message"])


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc):
    return error_response(request, 422, "INVALID_INPUT", "Check the supplied fields")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    request.state.request_id = str(uuid4())
    if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get("origin") != ORIGIN:
        response = error_response(request, 403, "FORBIDDEN", "Same-origin request required")
    elif int(request.headers.get("content-length", "0")) > (
        1000000 if request.url.path == "/api/v1/admin/registry" else 65536
    ):
        response = error_response(request, 422, "INVALID_INPUT", "Request body too large")
    else:
        try:
            response = await call_next(request)
        except (SQLAlchemyError, RuntimeError):
            response = error_response(request, 503, "UPSTREAM_UNAVAILABLE", "Service temporarily unavailable")
        except Exception:
            log.error(json.dumps({"request_id": request.state.request_id, "event": "request_failed"}))
            response = error_response(
                request, 500, "INTERNAL", "Request failed; use the request ID for support"
            )
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def owner(request: Request, conn, mutation: bool = False) -> str:
    token = request.cookies.get("lv_session", "")
    row = (
        conn.execute(
            select(db.sessions).where(
                db.sessions.c.capability_hash == sha(token), db.sessions.c.expires_at > now()
            )
        )
        .mappings()
        .first()
    )
    if not row:
        fail("UNAUTHORIZED", "Start a private browser session", 401)
    if mutation and not hmac.compare_digest(row["csrf_hash"], sha(request.headers.get("x-csrf-token", ""))):
        fail("FORBIDDEN", "Invalid CSRF token", 403)
    return row["id"]


def owned(conn, table, id: str, owner_id: str | None = None, lock: bool = False):
    query = select(table).where(table.c.id == id)
    if owner_id is not None:
        query = query.where(table.c.owner_id == owner_id)
    if lock:
        query = query.with_for_update()
    row = conn.execute(query).mappings().first()
    if not row:
        fail("NOT_FOUND", "Record not found", 404)
    return row


def if_match(request: Request, revision: int) -> None:
    if request.headers.get("if-match", "").strip('"') != str(revision):
        fail("REVISION_CONFLICT", "Refresh before changing this record", 409)


def as_response(request: Request, body, status: int = 200) -> Response:
    etag = '"' + str(body.get("revision", digest(body)) if isinstance(body, dict) else digest(body)) + '"'
    if request.method == "GET" and request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    return JSONResponse(body, status_code=status, headers={"ETag": etag})


def new_document(body: dict | None = None) -> dict:
    return {"schema_version": "1.0", "id": str(uuid4()), "revision": 1, **(body or {})}


@app.post("/api/v1/session", status_code=204)
def session(request: Request, response: Response):
    capability, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    with db.engine().begin() as conn:
        existing = (
            conn.execute(
                select(db.sessions).where(
                    db.sessions.c.capability_hash == sha(request.cookies.get("lv_session", "")),
                    db.sessions.c.expires_at > now(),
                )
            )
            .mappings()
            .first()
        )
        if existing:
            conn.execute(
                update(db.sessions).where(db.sessions.c.id == existing["id"]).values(csrf_hash=sha(csrf))
            )
        else:
            conn.execute(
                db.sessions.insert().values(
                    id=str(uuid4()),
                    capability_hash=sha(capability),
                    csrf_hash=sha(csrf),
                    expires_at=now() + timedelta(days=365),
                )
            )
            response.set_cookie(
                "lv_session",
                capability,
                httponly=True,
                samesite="strict",
                secure=os.environ.get("COOKIE_SECURE") == "true",
                max_age=31536000,
            )
            response.headers["X-Recovery-Key"] = capability
    response.set_cookie(
        "lv_csrf",
        csrf,
        httponly=False,
        samesite="strict",
        secure=os.environ.get("COOKIE_SECURE") == "true",
        max_age=31536000,
    )
    response.headers["X-CSRF-Token"] = csrf


@app.post("/api/v1/session/recover", status_code=204)
def recover(response: Response, body: dict = Body()):
    validate("TokenInput", body)
    with db.engine().begin() as conn:
        row = (
            conn.execute(
                select(db.sessions).where(
                    db.sessions.c.capability_hash == sha(body["token"]), db.sessions.c.expires_at > now()
                )
            )
            .mappings()
            .first()
        )
        if not row:
            fail("UNAUTHORIZED", "Recovery key not valid", 401)
        csrf = secrets.token_urlsafe(32)
        conn.execute(update(db.sessions).where(db.sessions.c.id == row["id"]).values(csrf_hash=sha(csrf)))
    response.set_cookie(
        "lv_session",
        body["token"],
        httponly=True,
        samesite="strict",
        secure=os.environ.get("COOKIE_SECURE") == "true",
        max_age=31536000,
    )
    response.set_cookie("lv_csrf", csrf, samesite="strict", secure=os.environ.get("COOKIE_SECURE") == "true")
    response.headers["X-CSRF-Token"] = csrf


@app.post("/api/v1/locations/resolve")
def location_resolve(request: Request, body: dict = Body()):
    validate("LocationInput", body)
    with db.engine().begin() as conn:
        own = owner(request, conn, True)
        zcta = body["zip"] is not None
        if zcta:
            result = resolve_zip(body["zip"])
            if "error" in result:
                fail("INVALID_INPUT", "Use a five-digit ZIP string")
            if result.get("status") == "unavailable":
                fail("UNSUPPORTED_LOCATION", "No Census representative point. Use GPS or manual coordinates.")
            lat, lon = result["latitude_deg"], result["longitude_deg"]
        else:
            lat, lon = body["latitude_deg"], body["longitude_deg"]
            if lat is None or lon is None:
                fail("INVALID_INPUT", "Both latitude and longitude are required")
        p = point(lat, lon, body["altitude_m"] or 0)
        zone = timezone_at(lat, lon)
        if not zone:
            fail("UNSUPPORTED_LOCATION", "Observer timezone unavailable")
        canonical = digest({"point": p, "zip": body["zip"]})
        db.lock(conn, "location-quota")
        existing = (
            conn.execute(
                select(db.locations).where(
                    db.locations.c.owner_id == own, db.locations.c.canonical == canonical
                )
            )
            .mappings()
            .first()
        )
        if existing:
            return as_response(request, existing["body"])
        if conn.scalar(select(func.count()).select_from(db.locations)) >= 100:
            fail("LIMIT_REACHED", "The pilot supports 100 active points; existing locations remain available")
        doc = new_document(
            {
                "zip": body["zip"],
                "point": p,
                "origin": "zcta" if zcta else "manual",
                "confirmed": False,
                "timezone": zone,
                "timezone_data_version": "tzdata-"
                + version("tzdata")
                + "/timezonefinder-data-"
                + version("timezonefinder-data"),
                "representative_point": zcta,
                "altitude_assumed": body["altitude_m"] is None,
                "provenance": [],
            }
        )
        if zcta:
            manifest = json.loads((ROOT / "evidence/build/dependency-manifest.json").read_text())
            doc["provenance"] = [
                {
                    "source_url": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_zcta_national.zip",
                    "sha256": manifest["files"]["data/gazetteer/census-2025.zip"],
                    "fetched_at": "2026-10-13T13:43:55.044115Z",
                    "issued_at": None,
                    "source_revision": "2025",
                    "license": "US Census Bureau public data",
                    "parser_version": "census-pipe-v1",
                    "kind": "provider",
                    "notes": ["Representative point, not a street address"],
                }
            ]
        conn.execute(
            db.locations.insert().values(
                id=doc["id"],
                revision=1,
                owner_id=own,
                body=doc,
                created_at=now(),
                expires_at=now() + timedelta(hours=24),
                canonical=canonical,
            )
        )
    return as_response(request, doc)


@app.post("/api/v1/locations/{id}/confirm")
def confirm(id: str, request: Request, body: dict = Body()):
    validate("ConfirmInput", body)
    with db.engine().begin() as conn:
        row = owned(conn, db.locations, id, owner(request, conn, True), True)
        if body["revision"] != row["revision"]:
            fail("REVISION_CONFLICT", "Location has changed", 409)
        doc = {**row["body"], "confirmed": True, "revision": row["revision"] + 1}
        conn.execute(
            update(db.locations).where(db.locations.c.id == id).values(body=doc, revision=doc["revision"])
        )
    return as_response(request, doc)


@app.get("/api/v1/locations/{id}")
def get_location(id: str, request: Request):
    with db.engine().connect() as conn:
        return as_response(request, owned(conn, db.locations, id, owner(request, conn))["body"])


@app.delete("/api/v1/locations/{id}", status_code=204)
def delete_location(id: str, request: Request):
    with db.engine().begin() as conn:
        own = owner(request, conn, True)
        row = owned(conn, db.locations, id, own, True)
        conn.execute(delete(db.cache).where(db.cache.c.key.like("assessment:" + own + ":%")))
        conn.execute(db.ledger.insert().values(id=id, deleted_at=now()))
        conn.execute(delete(db.locations).where(db.locations.c.id == id))
        from .privacy import purge_points

        purge_points(conn, [row["body"]])


def listing(request: Request, table, private: bool, limit: int, cursor: str | None) -> Response:
    with db.engine().connect() as conn:
        q = select(table)
        if private:
            q = q.where(table.c.owner_id == owner(request, conn))
        if cursor:
            q = q.where(table.c.id > cursor)
        rows = conn.execute(q.order_by(table.c.id).limit(limit + 1)).mappings().all()
        response = as_response(request, [row["body"] for row in rows[:limit]])
        if len(rows) > limit:
            response.headers["X-Next-Cursor"] = rows[limit - 1]["id"]
        return response


@app.get("/api/v1/launches")
def get_launches(request: Request, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
    return listing(request, db.launches, False, limit, cursor)


@app.get("/api/v1/launch-history")
def launch_history(request: Request, cursor: str | None = None):
    from .history import read_page

    try:
        result = read_page(cursor, now())
    except ValueError as exc:
        fail("INVALID_HISTORY_CURSOR", str(exc), 409)
    return as_response(request, result)


@app.get("/api/v1/launches/{id}")
def get_launch(id: str, request: Request):
    with db.engine().connect() as conn:
        return as_response(request, owned(conn, db.launches, id)["body"])


@app.get("/api/v1/locations/{id}/viewing-opportunities")
def viewing_opportunities(id: str, request: Request, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
    from .opportunities import summarize, within_viewing_horizon
    from packages.visibility.planning import calculate_plan

    with db.engine().begin() as conn:
        own = owner(request, conn)
        location = owned(conn, db.locations, id, own)["body"]
        if not location["confirmed"]:
            fail("UNCONFIRMED_LOCATION", "Confirm your viewing point first")
        query = select(db.launches).order_by(db.launches.c.id).limit(limit + 1)
        if cursor:
            query = query.where(db.launches.c.id > cursor)
        rows = conn.execute(query).mappings().all()
        # Most inventory entries have neither a supported family nor registered evidence.
        # Do not calculate astronomy or archive empty assessments for each schedule row.
        routed = set(conn.execute(select(db.routes.c.body["launch_id"].as_string())).scalars())
        weather = cached_weather(conn, location)
        at = now()
        summaries = []
        for row in rows[:limit]:
            launch = row["body"]
            if launch["id"] in routed:
                db.lock(conn, "assessment:" + launch["id"] + ":" + id)
                summaries.append(summarize(launch, assess(conn, launch, location, own, at)))
            else:
                summaries.append(summarize(launch, plan=calculate_plan(launch, location, weather, at)))
            if not within_viewing_horizon(launch, location, at):
                summaries[-1]["viewable"] = False
        response = as_response(request, summaries)
        if len(rows) > limit:
            response.headers["X-Next-Cursor"] = rows[limit - 1]["id"]
        return response


@app.post("/api/v1/assessments")
def create_assessment(request: Request, body: dict = Body()):
    validate("AssessmentInput", body)
    with db.engine().begin() as conn:
        own = owner(request, conn, True)
        loc = owned(conn, db.locations, body["location_id"], own)["body"]
        if not loc["confirmed"]:
            fail("UNCONFIRMED_LOCATION", "Confirm your viewing point first")
        launch = owned(conn, db.launches, body["launch_id"])["body"]
        db.lock(conn, "assessment:" + launch["id"] + ":" + loc["id"])
        result = assess(conn, launch, loc, own, now())
    return as_response(request, result)


@app.get("/api/v1/assessments/{id}")
def get_assessment(id: str, request: Request):
    with db.engine().connect() as conn:
        doc = owned(conn, db.assessments, id, owner(request, conn))["body"]
        response = as_response(request, doc)
        response.headers["X-Assessment-Archive"] = "immutable; request a new assessment for current advice"
        return response


@app.get("/api/v1/locations/{id}/weather")
def get_weather(id: str, request: Request):
    with db.engine().connect() as conn:
        loc = owned(conn, db.locations, id, owner(request, conn))["body"]
        return {
            "intervals": cached_weather(conn, loc),
            "note": "Weather alone cannot establish launch visibility",
        }


@app.get("/api/v1/launches/{id}/evidence")
def evidence(id: str):
    with db.engine().connect() as conn:
        owned(conn, db.launches, id)
        return (
            conn.execute(select(db.routes.c.body).where(db.routes.c.body["launch_id"].as_string() == id))
            .scalars()
            .all()
        )


@app.get("/api/v1/profiles/{id}")
def profile(id: str, request: Request):
    with db.engine().connect() as conn:
        return as_response(request, owned(conn, db.profiles, id)["body"])


def cancel_subscription(conn, row, at: datetime) -> None:
    body = {**row["body"], "enabled": False, "revision": row["revision"] + 1}
    conn.execute(
        update(db.subscriptions)
        .where(db.subscriptions.c.id == row["id"])
        .values(enabled=False, revision=body["revision"], body=body)
    )
    conn.execute(
        update(db.outbox)
        .where(
            db.outbox.c.subscription_id == row["id"], db.outbox.c.state.in_(["pending", "claimed", "retry"])
        )
        .values(state="cancelled")
    )


@app.post("/api/v1/subscriptions", status_code=201)
def subscribe(request: Request, body: dict = Body()):
    validate("SubscriptionInput", body)
    key = request.headers.get("idempotency-key", "")
    if len(key) < 16 or len(key) > 200:
        fail("INVALID_INPUT", "Idempotency-Key must be 16 to 200 characters")
    with db.engine().begin() as conn:
        own = owner(request, conn, True)
        db.lock(conn, "idempotency:" + own + key)
        prior = (
            conn.execute(
                select(db.idempotency).where(db.idempotency.c.owner_id == own, db.idempotency.c.key == key)
            )
            .mappings()
            .first()
        )
        if prior:
            if prior["request_hash"] != digest(body):
                fail("REVISION_CONFLICT", "Idempotency key already used for a different request", 409)
            return as_response(request, prior["body"], 201)
        loc = owned(conn, db.locations, body["location_id"], own, True)["body"]
        if not loc["confirmed"]:
            fail("UNCONFIRMED_LOCATION", "Confirm your location")
        if not body["all_supported_launches"] and not body["launch_ids"]:
            fail("INVALID_INPUT", "Select launches or all supported launches")
        for id in body["launch_ids"]:
            owned(conn, db.launches, id)
        token, at = secrets.token_urlsafe(48), now()
        doc = new_document(
            {
                **body,
                "channel": "in_app",
                "enabled": True,
                "quiet_start": "22:00",
                "quiet_end": "07:00",
                "created_at": stamp(at),
                "consented_at": stamp(at),
                "email_verified": False,
                "deleted_at": None,
            }
        )
        conn.execute(
            db.subscriptions.insert().values(
                id=doc["id"],
                revision=1,
                body=doc,
                owner_id=own,
                location_id=loc["id"],
                enabled=True,
                unsubscribe_hash=sha(token),
                created_at=at,
            )
        )
        conn.execute(update(db.locations).where(db.locations.c.id == loc["id"]).values(expires_at=None))
        conn.execute(
            db.idempotency.insert().values(
                owner_id=own, key=key, request_hash=digest(body), body=doc, created_at=at
            )
        )
        response = as_response(request, doc, 201)
        response.headers["X-Unsubscribe-Token"] = token
        return response


@app.get("/api/v1/subscriptions")
def subscriptions(request: Request, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
    return listing(request, db.subscriptions, True, limit, cursor)


@app.put("/api/v1/subscriptions/{id}")
def change_subscription(id: str, request: Request, body: dict = Body()):
    validate("SubscriptionInput", body)
    with db.engine().begin() as conn:
        own = owner(request, conn, True)
        row = owned(conn, db.subscriptions, id, own, True)
        if_match(request, row["revision"])
        loc = owned(conn, db.locations, body["location_id"], own)["body"]
        if not loc["confirmed"]:
            fail("UNCONFIRMED_LOCATION", "Confirm your location")
        if not body["all_supported_launches"] and not body["launch_ids"]:
            fail("INVALID_INPUT", "Select launches or all supported launches")
        for launch_id in body["launch_ids"]:
            owned(conn, db.launches, launch_id)
        conn.execute(update(db.locations).where(db.locations.c.id == loc["id"]).values(expires_at=None))
        doc = {**row["body"], **body, "revision": row["revision"] + 1}
        conn.execute(
            update(db.subscriptions)
            .where(db.subscriptions.c.id == id)
            .values(body=doc, revision=doc["revision"], location_id=body["location_id"])
        )
        conn.execute(
            update(db.outbox)
            .where(db.outbox.c.subscription_id == id, db.outbox.c.state.in_(["pending", "claimed", "retry"]))
            .values(state="cancelled")
        )
    return as_response(request, doc)


@app.delete("/api/v1/subscriptions/{id}", status_code=204)
def unsubscribe_owned(id: str, request: Request):
    with db.engine().begin() as conn:
        row = owned(conn, db.subscriptions, id, owner(request, conn, True), True)
        cancel_subscription(conn, row, now())


@app.post("/api/v1/unsubscribe", status_code=204)
def unsubscribe(body: dict = Body()):
    validate("TokenInput", body)
    with db.engine().begin() as conn:
        row = (
            conn.execute(
                select(db.subscriptions)
                .where(db.subscriptions.c.unsubscribe_hash == sha(body["token"]))
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if not row:
            fail("NOT_FOUND", "Unsubscribe token not found", 404)
        cancel_subscription(conn, row, now())


@app.get("/api/v1/notifications")
def notifications(request: Request, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
    return listing(request, db.notices, True, limit, cursor)


@app.delete("/api/v1/privacy", status_code=204)
def privacy(request: Request, response: Response):
    with db.engine().begin() as conn:
        own = owner(request, conn, True)
        point_docs = list(
            conn.execute(select(db.locations.c.body).where(db.locations.c.owner_id == own)).scalars()
        )
        rows = (
            conn.execute(select(db.subscriptions).where(db.subscriptions.c.owner_id == own).with_for_update())
            .mappings()
            .all()
        )
        for row in rows:
            cancel_subscription(conn, row, now())
        conn.execute(db.ledger.insert().values(id=own, deleted_at=now()))
        conn.execute(delete(db.cache).where(db.cache.c.key.like("assessment:" + own + ":%")))
        for row in rows:
            conn.execute(delete(db.cache).where(db.cache.c.key.like("downgrade:" + row["id"] + ":%")))
        conn.execute(delete(db.sessions).where(db.sessions.c.id == own))
        from .privacy import purge_points

        purge_points(conn, point_docs)
    response.delete_cookie("lv_session")
    response.delete_cookie("lv_csrf")


@app.post("/api/v1/observations", status_code=201)
def observation(request: Request, body: dict = Body()):
    validate("ObservationInput", body)
    if not body["consent_to_archive"]:
        fail("CONSENT_REQUIRED", "Archive consent is required")
    with db.engine().begin() as conn:
        own = owner(request, conn, True)
        forecast = owned(conn, db.assessments, body["assessment_id"], own)["body"]
        at = utc(body["observed_at"])
        if at > now() + timedelta(minutes=5) or (
            at < utc(forecast["computed_at"]) and not body.get("retrospective", False)
        ):
            fail("INVALID_INPUT", "Observation must follow the archived forecast and cannot be in the future")
        launch = owned(conn, db.launches, forecast["launch_id"])["body"]
        launch_at = launch["actual_liftoff"] or launch["net"]
        if body["outcome"] in ("seen", "not_seen") and (not launch_at or at < utc(launch_at)):
            fail("INVALID_INPUT", "A seen/not-seen report must follow the launch opportunity")
        retrospective = bool(
            body.get("retrospective", False)
            or not launch_at
            or utc(forecast["computed_at"]) >= utc(launch_at)
            or at < utc(forecast["computed_at"])
        )
        doc = new_document(
            {
                **body,
                "retrospective": retrospective,
                "launch_id": forecast["launch_id"],
                "location_id": forecast["location_id"],
                "provenance": [],
            }
        )
        conn.execute(
            db.observations.insert().values(
                id=doc["id"],
                revision=1,
                body=doc,
                owner_id=own,
                assessment_id=forecast["id"],
                created_at=now(),
            )
        )
    return as_response(request, doc, 201)


def require_admin(request: Request, conn) -> None:
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    row = (
        conn.execute(select(db.cache).where(db.cache.c.key == "admin-session:" + sha(token)))
        .mappings()
        .first()
    )
    if not row or not row["next_at"] or row["next_at"] <= now():
        fail("UNAUTHORIZED", "Operator authentication required", 401)


@app.post("/api/v1/admin/session")
def admin_session(request: Request, body: dict = Body()):
    from services.worker.ingestion import reserve

    if not reserve("admin-auth:" + sha(request.client.host if request.client else "local"), now()):
        fail("RATE_LIMITED", "Admin authentication rate limited", 429)
    secret = body.get("secret")
    expected = os.environ.get("ADMIN_SECRET_HASH", "")
    if not isinstance(secret, str) or not expected or not hmac.compare_digest(sha(secret), expected):
        fail("UNAUTHORIZED", "Operator authentication required", 401)
    token = secrets.token_urlsafe(48)
    expiry = now() + timedelta(minutes=15)
    with db.engine().begin() as conn:
        conn.execute(
            db.cache.insert().values(key="admin-session:" + sha(token), body={}, next_at=expiry, failures=0)
        )
    return {"token": token, "expires_at": stamp(expiry)}


@app.patch("/api/v1/admin/launches/{id}")
def admin_launch(id: str, request: Request, body: dict = Body()):
    validate("AdminInput", body)
    with db.engine().begin() as conn:
        require_admin(request, conn)
        row = owned(conn, db.launches, id, lock=True)
        if body["revision"] != row["revision"]:
            fail("REVISION_CONFLICT", "Refresh mission revision", 409)
        doc = {**row["body"], "disabled": body["disabled"], "revision": row["revision"] + 1}
        corrections = {k: body[k] for k in ("status", "recovery_configuration") if k in body}
        if corrections:
            if not body.get("source_url", "").startswith("https://"):
                fail("INVALID_INPUT", "A reviewed public source URL is required for a mission correction")
            doc.update(corrections)
            from sqlalchemy.dialects.postgresql import insert

            conn.execute(
                insert(db.cache)
                .values(
                    key="reviewed-mission:" + id,
                    body={
                        "source_updated_at": row["body"]["source_updated_at"],
                        "corrections": corrections,
                        "source_url": body["source_url"],
                    },
                    failures=0,
                )
                .on_conflict_do_update(
                    index_elements=["key"],
                    set_={
                        "body": {
                            "source_updated_at": row["body"]["source_updated_at"],
                            "corrections": corrections,
                            "source_url": body["source_url"],
                        }
                    },
                )
            )
        conn.execute(
            update(db.launches)
            .where(db.launches.c.id == id)
            .values(body=doc, revision=doc["revision"], disabled=body["disabled"], status=doc["status"])
        )
        conn.execute(
            db.revisions.insert().values(
                id=str(uuid4()), launch_id=id, revision=doc["revision"], body=doc, created_at=now()
            )
        )
        conn.execute(
            update(db.outbox)
            .where(db.outbox.c.launch_id == id, db.outbox.c.state.in_(["pending", "claimed", "retry"]))
            .values(state="cancelled")
        )
        conn.execute(
            db.audit.insert().values(
                id=str(uuid4()),
                revision=1,
                body={
                    "actor": "operator",
                    "action": "mission_corrected"
                    if corrections
                    else "mission_disabled"
                    if body["disabled"]
                    else "mission_enabled",
                    "corrections": corrections,
                    "source_url": body.get("source_url"),
                    "target": id,
                    "revision": doc["revision"],
                    "reason": body["reason"],
                },
                created_at=now(),
            )
        )
    return as_response(request, doc)


@app.get("/api/v1/admin/ingestion")
def admin_ingestion(request: Request):
    with db.engine().connect() as conn:
        require_admin(request, conn)
        rows = conn.execute(select(db.cache)).mappings().all()
        return [
            {
                "id": sha(r["key"]),
                "source": "NWS" if "weather.gov" in r["key"] or r["key"].startswith("point:") else r["key"],
                "last_success_at": stamp(r["last_success_at"]) if r["last_success_at"] else None,
                "next_at": stamp(r["next_at"]) if r["next_at"] else None,
                "error": r["error"],
                "failures": r["failures"],
            }
            for r in rows
        ]


@app.post("/api/v1/admin/ingestion/{id}/retry", status_code=202)
def admin_retry(id: str, request: Request):
    with db.engine().begin() as conn:
        require_admin(request, conn)
        rows = conn.execute(select(db.cache)).mappings().all()
        row = next((r for r in rows if sha(r["key"]) == id), None)
        if not row:
            fail("NOT_FOUND", "Ingestion source not found", 404)
        if row["next_at"] and row["next_at"] > now() and row["error"] in ("HTTP_403", "HTTP_429"):
            fail("RATE_LIMITED", "Source backoff must expire before retry", 429)
        conn.execute(update(db.cache).where(db.cache.c.key == row["key"]).values(next_at=now()))
        conn.execute(
            db.audit.insert().values(
                id=str(uuid4()),
                revision=1,
                body={"actor": "operator", "action": "retry_ingestion", "target": id},
                created_at=now(),
            )
        )


@app.get("/api/v1/health/live")
def live():
    return {"status": "ok", "checked_at": stamp(now()), "components": []}


@app.get("/api/v1/health/ready")
def ready():
    components = []
    try:
        with db.engine().connect() as conn:
            migration = conn.scalar(text("SELECT version_num FROM alembic_version"))
        if migration != "0002":
            raise RuntimeError("migration")
        components.append(
            {"name": "database", "status": "ok", "last_success_at": stamp(now()), "reason": None}
        )
        model_manifest()
        components.append(
            {"name": "astronomy", "status": "ok", "last_success_at": stamp(now()), "reason": None}
        )
        with db.engine().connect() as conn:
            heartbeat = conn.scalar(
                select(db.cache.c.last_success_at).where(db.cache.c.key == "worker-heartbeat")
            )
        components.append(
            {
                "name": "worker",
                "status": "ok" if heartbeat and now() - heartbeat < timedelta(minutes=3) else "degraded",
                "last_success_at": stamp(heartbeat) if heartbeat else None,
                "reason": None if heartbeat else "No worker heartbeat yet",
            }
        )
    except Exception:
        return JSONResponse(
            {
                "status": "unavailable",
                "checked_at": stamp(now()),
                "components": [
                    {
                        "name": "readiness",
                        "status": "unavailable",
                        "last_success_at": None,
                        "reason": "Database, migration or local model asset unavailable",
                    }
                ],
            },
            status_code=503,
        )
    return {
        "status": "degraded" if any(c["status"] != "ok" for c in components) else "ok",
        "checked_at": stamp(now()),
        "components": components,
    }


@app.get("/api/v1/launches/{id}/calendar")
def calendar(id: str, request: Request, location_id: str):
    from .calendar import calendar_snapshot

    with db.engine().begin() as conn:
        own = owner(request, conn)
        launch = owned(conn, db.launches, id)["body"]
        location = owned(conn, db.locations, location_id, own)["body"]
        result = assess(conn, launch, location, own, now())
        try:
            content = calendar_snapshot(launch, location, result, now())
        except ValueError:
            fail("UNSUPPORTED_TIME", "Calendar time unavailable for this schedule precision")
    return Response(
        content,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="launch-visibility.ics"'},
    )


@app.post("/api/v1/subscriptions/preview")
def preview_subscription(request: Request, body: dict = Body()):
    from services.worker.notifications import milestone_preview

    validate("SubscriptionInput", body)
    at = now()
    with db.engine().begin() as conn:
        own = owner(request, conn, True)
        loc = owned(conn, db.locations, body["location_id"], own)["body"]
        if not loc["confirmed"]:
            fail("UNCONFIRMED_LOCATION", "Confirm a viewing point first")
        query = select(db.launches.c.body).where(db.launches.c.status == "scheduled")
        if not body["all_supported_launches"]:
            query = query.where(db.launches.c.id.in_(body["launch_ids"]))
        previews = []
        sub = {**body, "created_at": stamp(at)}
        for launch in conn.execute(query.limit(100)).scalars():
            result = assess(conn, launch, loc, own, at)
            previews.append(
                {
                    "launch_id": launch["id"],
                    "name": launch["name"],
                    "advice": result["advice"],
                    "milestones": milestone_preview(sub, result, launch, loc, at),
                    "reason": "No supported viewing interval"
                    if not result.get("supported_intervals")
                    else "Future milestones only",
                }
            )
        return previews


@app.get("/api/v1/admin/metrics")
def metrics(request: Request):
    with db.engine().connect() as conn:
        require_admin(request, conn)
        at = now()
        pending = conn.scalar(
            select(func.count())
            .select_from(db.jobs)
            .where(db.jobs.c.state.in_(["pending", "claimed", "retry"]))
        )
        budget_rows = conn.execute(
            select(db.budget.c.provider, func.count())
            .where(db.budget.c.requested_at > at - timedelta(hours=1))
            .group_by(db.budget.c.provider)
        ).all()
        from .pilot import coverage

        return {
            "pending_jobs": pending,
            "provider_requests_last_hour": dict(budget_rows),
            "coverage": coverage(conn),
            "email_enabled": False,
            "mandatory_subscription_cost_usd": 0,
        }


@app.get("/api/v1/admin/audit")
def get_audit(request: Request):
    with db.engine().connect() as conn:
        require_admin(request, conn)
        return (
            conn.execute(select(db.audit.c.body).order_by(db.audit.c.created_at.desc()).limit(100))
            .scalars()
            .all()
        )


@app.get("/api/v1/locations")
def get_locations(request: Request, limit: int = Query(50, ge=1, le=100), cursor: str | None = None):
    return listing(request, db.locations, True, limit, cursor)


@app.post("/api/v1/admin/registry", status_code=201)
def registry_import(request: Request, body: dict = Body()):
    from .registry import import_document

    with db.engine().begin() as conn:
        require_admin(request, conn)
        try:
            return import_document(conn, body, now())
        except (ValueError, jsonschema.ValidationError):
            fail(
                "INVALID_INPUT",
                "Registry rejected: verify schema, source hash, permission review, identity and compatibility",
            )
