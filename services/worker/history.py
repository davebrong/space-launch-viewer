"""Shared, budgeted historical pages; browsing never fetches providers in the API."""

from datetime import datetime
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select, update

from services.api import db
from services.api.history import HEAD_KEY, HEAD_URL, page_key, page_url
from .ingestion import fetch


def refresh_page(snapshot: str, offset: int, at: datetime, client=None) -> None:
    if offset < 0 or offset % 100:
        raise ValueError("Invalid history offset")
    url = HEAD_URL
    if offset:
        with db.engine().connect() as conn:
            head = conn.execute(select(db.cache).where(db.cache.c.key == HEAD_KEY)).mappings().first()
        if not head or not head["last_success_at"] or head["body"]["provenance"]["sha256"] != snapshot:
            return
        if offset >= head["body"]["payload"]["count"]:
            return
        url = page_url(head["body"], offset)
    key = page_key(snapshot, offset)
    with db.engine().connect() as conn:
        previous = conn.execute(select(db.cache).where(db.cache.c.key == key)).mappings().first()
    result = fetch(url, key, "ll2", at, 3600 if not offset else 86400, client=client, budget_limit=11)
    if result and result["payload"].get("next"):
        parsed, expected = urlparse(result["payload"]["next"]), urlparse(url)
        expected_query = parse_qs(expected.query)
        expected_query["offset"] = [str(offset + 100)]
        if (
            parsed.scheme != "https"
            or parsed.netloc != expected.netloc
            or parsed.path != expected.path
            or parsed.fragment
            or parse_qs(parsed.query) != expected_query
        ):
            with db.engine().begin() as conn:
                conn.execute(
                    update(db.cache)
                    .where(db.cache.c.key == key)
                    .values(
                        error="INVALID_HISTORY_NEXT",
                        body=previous["body"] if previous else {},
                        last_success_at=previous["last_success_at"] if previous else None,
                    )
                )
