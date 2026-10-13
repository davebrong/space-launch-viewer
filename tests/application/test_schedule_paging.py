import copy
import json
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

import httpx
import pytest
from sqlalchemy import func, select

from services.api import db
from services.worker.ingestion import LL2_URL, refresh_schedule, schedule_page_url
from tests.application import support as s


def page(offset: int) -> dict:
    raw = json.loads((s.ROOT / "tests/fixtures/raw/ll2.json").read_text(encoding="utf-8"))["results"][0]
    raw["pad"].update(latitude=28.608, longitude=-80.604, location={"id": 12})
    rows = []
    for index in range(offset, min(offset + 100, 205)):
        item = copy.deepcopy(raw)
        item["id"] = str(uuid5(NAMESPACE_URL, "synthetic-pagination:" + str(index)))
        item["name"] = "SYNTHETIC PAGINATION " + str(index)
        rows.append(item)
    return {
        "count": 205,
        "results": rows,
        "next": LL2_URL.replace("12,27", "12%2C27") + "&offset=" + str(offset + 100)
        if offset < 200
        else None,
    }


def test_all_pages_cached_and_partial_failure_resumes():
    calls = []
    failing = True

    def upstream(request):
        offset = int(request.url.params.get("offset", 0))
        calls.append(offset)
        if offset == 100 and failing:
            return httpx.Response(429, headers={"Retry-After": "3600"})
        return httpx.Response(200, json=page(offset))

    with s.isolated_database(), httpx.Client(transport=httpx.MockTransport(upstream)) as client:
        first = refresh_schedule(s.AT, client=client)
        assert first["error"] == "HTTP_429" and not first["complete"]
        assert first["ingested"] == 100 and calls == [0, 100]
        failing = False
        # Do not bypass Retry-After. Keep the first page and resume next hour.
        refresh_schedule(s.AT + timedelta(minutes=1), client=client)
        assert calls == [0, 100]
        result = refresh_schedule(s.AT + timedelta(hours=1, seconds=1), client=client)
        assert result["complete"] and result["ingested"] == result["provider_count"] == 205
        assert result["pages"] == 3
        with db.engine().connect() as conn:
            assert conn.scalar(select(func.count()).select_from(db.launches)) == 205
            assert conn.scalar(select(func.count()).select_from(db.revisions)) == 205
        previous_calls = calls.copy()
        assert refresh_schedule(s.AT + timedelta(hours=1, minutes=1), client=client)["complete"]
        assert calls == previous_calls


def test_broad_pages_preserve_imminent_budget_slot():
    calls = []

    def upstream(request):
        calls.append(str(request.url))
        return httpx.Response(200, json=page(0))

    with s.isolated_database(), httpx.Client(transport=httpx.MockTransport(upstream)) as client:
        with db.engine().begin() as conn:
            conn.execute(db.budget.insert(), [{"provider": "ll2", "requested_at": s.AT}] * 10)
        result = refresh_schedule(s.AT, near=True, client=client)
        assert result["error"] == "BUDGET_DEFERRED" and len(calls) == 1
        assert not result["complete"] and result["ingested"] == 100


def test_pagination_rejects_source_changes_and_cycles():
    assert schedule_page_url(page(0)["next"], 0) == (LL2_URL + "&offset=100", 100)
    for bad in (
        12,
        "https://127.0.0.1/?offset=100",
        page(0)["next"].replace("upcoming/", "previous/"),
        page(0)["next"].replace("12%2C27", "1"),
        page(0)["next"] + "&offset=200",
        page(0)["next"] + "#fragment",
        page(0)["next"].replace("offset=100", "offset=0"),
    ):
        with pytest.raises(ValueError):
            schedule_page_url(bad, 0)


def test_overlapping_provider_pages_never_claim_complete():
    def upstream(request):
        offset = int(request.url.params.get("offset", 0))
        payload = page(offset)
        if offset == 100:
            payload["results"][0] = page(0)["results"][0]
        return httpx.Response(200, json=payload)

    with s.isolated_database(), httpx.Client(transport=httpx.MockTransport(upstream)) as client:
        result = refresh_schedule(s.AT, client=client)
        assert not result["complete"] and result["error"] == "SCHEDULE_PAGE_OVERLAP"
        assert result["ingested"] == 100
