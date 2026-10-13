"""Isolated PostgreSQL + actual API + real UI for synthetic browser edge cases.

Never packaged in the production image. No upstream calls or fake production rows.
"""

import os
import hashlib

os.environ["APP_ORIGIN"] = "http://127.0.0.1:3091"
os.environ["ADMIN_SECRET_HASH"] = hashlib.sha256(b"synthetic-browser-operator-secret").hexdigest()

from datetime import datetime, timezone, timedelta
from fastapi import Request
from fastapi.responses import Response
from sqlalchemy import update, delete
from sqlalchemy.dialects.postgresql import insert
import httpx
import uvicorn

from tests.application import support as s
from services.api import db
from services.api.main import app, owner, owned
from packages.visibility.common import stamp, utc


@app.post("/api/v1/__test__/seed")
def seed(request: Request, body: dict):
    at = datetime.now(timezone.utc)
    with db.engine().begin() as conn:
        own = owner(request, conn, True)
        loc = owned(conn, db.locations, body["location_id"], own)["body"]
    launch = s.launch(at)
    mode = body["mode"]
    launch["name"] = "SYNTHETIC TEST | " + mode
    if mode == "date":
        launch.update(time_precision="date", date_label=launch["net"][:10], date_basis_timezone="UTC")
    elif mode == "unknown":
        # Preserve a provider placeholder to ensure the UI does not invent its date.
        launch.update(time_precision="unknown")
    elif mode == "window":
        launch.update(
            time_precision="window",
            window={"start": launch["net"], "end": stamp(utc(launch["net"]) + timedelta(minutes=10))},
        )
    elif mode in ("scrubbed", "completed", "hold"):
        launch["status"] = mode
        if mode == "completed":
            launch.update(
                net=stamp(at - timedelta(hours=1)), actual_liftoff=stamp(at - timedelta(minutes=55))
            )
    route, profile = s.route(launch, loc, at), s.profile(launch)
    profile["provenance"] = [s.provenance(at)]
    if mode == "official":
        route.update(
            evidence_type="official_guidance",
            source_format="reviewed-guidance-v1",
            path_vertices=[],
            guidance={
                "observer_region": "SYNTHETIC Maryland",
                "membership": "included",
                "membership_method": "verified_coordinates",
                "viewing_interval": None,
                "relative_start_s": 300,
                "relative_end_s": 600,
                "timing_basis": "liftoff_relative",
                "timing_change_policy": "source_relative_valid",
                "boundary_uncertainty_m": 0,
                "location_id": loc["id"],
            },
        )
    elif mode == "hazard":
        route.update(evidence_type="hazard_corridor", source_format="reviewed-hazard-v1", path_vertices=[])
    elif mode == "stale":
        route["provenance"] = [s.provenance(at - timedelta(days=2))]
    coord = f"{loc['point']['latitude_deg']:.4f},{loc['point']['longitude_deg']:.4f}"
    with db.engine().begin() as conn:
        conn.execute(
            update(db.launches)
            .where(db.launches.c.id == launch["id"])
            .values(body=launch, status=launch["status"])
        )
        conn.execute(db.routes.insert().values(id=route["id"], revision=1, body=route, created_at=at))
        conn.execute(db.profiles.insert().values(id=profile["id"], revision=1, body=profile, created_at=at))
        for key, value in (
            ("point:" + coord, {"payload": {"properties": {"forecastGridData": "synthetic-grid"}}}),
            (
                "synthetic-grid",
                {
                    "provenance": s.provenance(at),
                    "payload": {
                        "properties": {
                            "updateTime": stamp(at),
                            "skyCover": {
                                "uom": "wmoUnit:percent",
                                "values": [
                                    {"validTime": stamp(at - timedelta(days=1)) + "/P4D", "value": 10}
                                ],
                            },
                        }
                    },
                },
            ),
        ):
            conn.execute(
                insert(db.cache)
                .values(key=key, body=value, failures=0)
                .on_conflict_do_update(index_elements=["key"], set_={"body": value})
            )
    return {"id": launch["id"]}


@app.delete("/api/v1/__test__/launches")
def empty(request: Request):
    with db.engine().begin() as conn:
        owner(request, conn, True)
        # This isolated fixture database is discarded on test-server shutdown.
        conn.execute(delete(db.notices))
        conn.execute(delete(db.outbox))
        conn.execute(delete(db.assessments))
        conn.execute(delete(db.attempts))
        conn.execute(delete(db.revisions))
        conn.execute(delete(db.launches))
    return {"empty": True}


@app.api_route("/{path:path}", methods=["GET"])
async def frontend(path: str, request: Request):
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        forwarded = {
            k: v
            for k, v in request.headers.items()
            if k.lower() in ("rsc", "next-router-state-tree", "next-router-prefetch", "next-url", "accept")
        }
        r = await client.get("http://127.0.0.1:3080/" + path, params=request.query_params, headers=forwarded)
    headers = {
        k: v
        for k, v in r.headers.items()
        if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")
    }
    return Response(r.content, status_code=r.status_code, headers=headers)


if __name__ == "__main__":
    with s.isolated_database():
        uvicorn.run(app, host="127.0.0.1", port=3091, access_log=False)
