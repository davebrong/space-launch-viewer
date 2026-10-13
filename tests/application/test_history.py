from datetime import timedelta
from unittest.mock import patch

import httpx
from sqlalchemy import select, func

from services.api import db
from services.api.history import read_page, HEAD_URL
from services.worker.history import refresh_page
from tests.application import support as s
from tests.application.test_schedule_paging import page
from services.api.main import validate


def historical(offset=0, anchor=None):
    body = page(offset)
    for i, row in enumerate(body["results"]):
        row["net"] = (s.AT - timedelta(days=offset + i)).isoformat().replace("+00:00", "Z")
        row["status"] = {"id": 3, "name": "Launch Successful"}
        row["pad"]["name"] = "SYNTHETIC Cape pad"
    suffix = "&net__lte=" + anchor if anchor else ""
    body["next"] = HEAD_URL + suffix + "&offset=" + str(offset + 100) if offset < 200 else None
    return body


def test_history_api_is_worker_owned_paginated_and_not_location_filtered():
    def upstream(request):
        return httpx.Response(
            200, json=historical(int(request.url.params.get("offset", 0)), request.url.params.get("net__lte"))
        )

    with (
        s.isolated_database(),
        httpx.Client(transport=httpx.MockTransport(upstream)) as source,
        patch("services.api.main.now", return_value=s.AT),
    ):
        client = s.client()
        initial = client.get("/api/v1/launch-history").json()
        assert initial["state"] == "pending" and initial["rows"] == []
        with db.engine().connect() as conn:
            assert conn.scalar(select(func.count()).select_from(db.budget)) == 0
            assert conn.scalar(select(func.count()).select_from(db.jobs)) == 1
        refresh_page("", 0, s.AT, client=source)
        first = client.get("/api/v1/launch-history").json()
        assert first["state"] == "ready" and first["provider_count"] == 205 and len(first["rows"]) == 100
        assert first["rows"][0]["status"] == "Launch Successful"
        assert first["fetched_at"] and first["rows"][0]["updated_at"]
        cursor = first["next_cursor"]
        snapshot = cursor.split(":")[0]
        assert client.get("/api/v1/launch-history", params={"cursor": cursor}).json()["state"] == "pending"
        refresh_page(snapshot, 100, s.AT, client=source)
        second = client.get("/api/v1/launch-history", params={"cursor": cursor}).json()
        assert len(second["rows"]) == 100
        assert not {r["id"] for r in first["rows"]} & {r["id"] for r in second["rows"]}
        assert "net__lte=" in second["source_url"]
        refresh_page(snapshot, 200, s.AT, client=source)
        last = read_page(second["next_cursor"], s.AT)
        assert len(last["rows"]) == 5 and last["next_cursor"] is None
        for bad in ("https://evil.test", snapshot + ":1", snapshot + ":999900", "0" * 64 + ":100"):
            assert client.get("/api/v1/launch-history", params={"cursor": bad}).status_code == 409
        with db.engine().connect() as conn:
            assert (
                conn.scalar(select(func.count()).select_from(db.launches)) == 0
            )  # historical browse doesn't pollute forecast inventory


def test_history_respects_retry_after_budget_and_preserves_last_good_page():
    calls = []
    fail = False
    invalid = False

    def upstream(request):
        calls.append(str(request.url))
        if fail:
            return httpx.Response(429, headers={"Retry-After": "7200"})
        body = historical()
        if invalid:
            body["next"] = "https://evil.test/history"
        return httpx.Response(200, json=body)

    with s.isolated_database(), httpx.Client(transport=httpx.MockTransport(upstream)) as source:
        refresh_page("", 0, s.AT, client=source)
        first = read_page(None, s.AT)
        fail = True
        later = s.AT + timedelta(hours=1, seconds=1)
        refresh_page("", 0, later, client=source)
        stale = read_page(None, later)
        assert stale["rows"] == first["rows"] and stale["error"] == "HTTP_429"
        refresh_page("", 0, later + timedelta(minutes=1), client=source)
        assert len(calls) == 2
        fail = False
        invalid = True
        refresh_page("", 0, later + timedelta(hours=2, seconds=1), client=source)
        assert read_page(None, later + timedelta(hours=2, seconds=2))["rows"] == first["rows"]
    with s.isolated_database(), httpx.Client(transport=httpx.MockTransport(upstream)) as source:
        with db.engine().begin() as conn:
            conn.execute(db.budget.insert(), [{"provider": "ll2", "requested_at": s.AT}] * 11)
        before = len(calls)
        refresh_page("", 0, s.AT, client=source)
        assert len(calls) == before and read_page(None, s.AT)["error"] == "BUDGET_DEFERRED"


def test_historical_detail_uses_owned_zip_shared_model_and_never_creates_future_launches():
    body = historical()
    raw = body["results"][0]
    raw["name"] = "SYNTHETIC Falcon Heavy | Past launch"
    raw["net"] = "2025-10-01T12:00:00Z"
    raw["net_precision"] = {"id": 1}
    legacy = body["results"][1]
    legacy["net_precision"] = None
    legacy["status"] = {"id": 4, "name": "Launch Failure"}
    with (
        s.isolated_database(),
        httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))) as source,
        patch("services.api.main.now", return_value=s.AT),
    ):
        refresh_page("", 0, s.AT, client=source)
        client = s.client()
        near = s.location(client, "fl-zip")
        far = s.location(client, "md-zip")
        path = "/api/v1/launch-history/" + raw["id"]
        result = client.get(path, params={"location_id": near["id"]})
        assert result.status_code == 200, result.text
        doc = result.json()
        validate("HistoricalLaunchDetail", doc)
        plan = doc["assessment"]["planning_scenario"]
        assert plan["kind"] == "near_launch_site"
        assert plan["watch_interval"] == {"start": "2025-10-01T11:58:00Z", "end": "2025-10-01T12:05:00Z"}
        assert plan["directions"] and not plan["uses_sightings"]
        assert plan["cloud_cover_min_pct"] is None
        distant = client.get(path, params={"location_id": far["id"]}).json()
        assert distant["assessment"]["planning_scenario"] is None
        old = client.get("/api/v1/launch-history/" + legacy["id"], params={"location_id": near["id"]}).json()
        assert old["time_precision_unspecified"] and old["source_status"] == "Launch Failure"
        assert old["assessment"]["planning_scenario"]["watch_interval"] is None
        other = s.client()
        assert other.get(path, params={"location_id": near["id"]}).status_code == 404
        assert (
            client.get("/api/v1/launch-history/missing", params={"location_id": near["id"]}).status_code
            == 404
        )
        with db.engine().connect() as conn:
            assert conn.scalar(select(func.count()).select_from(db.launches)) == 0
            assert conn.scalar(select(func.count()).select_from(db.assessments)) == 0
            assert conn.scalar(select(func.count()).select_from(db.budget)) == 1
