from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from sqlalchemy import select, func, update
from sqlalchemy.dialects.postgresql import insert

from services.api import db
from services.api.config import DATA
from services.api.adapters import ll2, nws
from packages.visibility.common import stamp, utc, digest

LL2_URL = "https://ll.thespacedevs.com/2.3.0/launches/upcoming/?limit=100&location__ids=12,27"


def approved_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        return False
    if parsed.hostname in ("www.nasa.gov", "www.spacex.com") and parsed.path == "/robots.txt":
        return True
    if parsed.hostname == "www.nasa.gov" and parsed.path.startswith("/blogs/"):
        return True
    if parsed.hostname == "www.spacex.com" and parsed.path.startswith("/launches/"):
        return True
    return (
        parsed.hostname == "ll.thespacedevs.com"
        and (
            parsed.path.startswith("/2.3.0/launches/")
            or parsed.path in ("/2.3.0/config/launch_statuses/", "/2.3.0/config/net_precisions/")
        )
    ) or (
        parsed.hostname == "api.weather.gov"
        and bool(re.fullmatch(r"/(?:points/[-\d.,]+|gridpoints/[A-Z]{3}/\d+,\d+)", parsed.path))
    )


def budget_allowed(count: int, limit: int = 12) -> bool:
    return count < limit


def reserve(provider: str, now: datetime, limit: int | None = None) -> bool:
    with db.engine().begin() as conn:
        db.lock(conn, "budget:" + provider)
        count = conn.scalar(
            select(func.count())
            .select_from(db.budget)
            .where(db.budget.c.provider == provider, db.budget.c.requested_at > now - timedelta(hours=1))
        )
        if not budget_allowed(
            count,
            min(limit or 12, 12) if provider == "ll2" else 20 if provider.startswith("admin-auth:") else 500,
        ):
            return False
        conn.execute(db.budget.insert().values(provider=provider, requested_at=now))
        return True


def atomic_snapshot(content: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(content).hexdigest()
    folder = DATA / "snapshots"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (sha + ".json")
    if not target.exists():
        fd, path = tempfile.mkstemp(dir=folder)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(path, target)
        finally:
            if os.path.exists(path):
                os.unlink(path)
    return sha, str(target)


def failure_policy(has_cache: bool) -> dict:
    return {"cached_data_retained": has_cache, "positive_notices": False, "paid_fallback": False}


def fetch(
    url: str,
    key: str,
    provider: str,
    now: datetime,
    period_s: int,
    client=None,
    budget_limit: int | None = None,
) -> dict | None:
    if not approved_url(url):
        raise ValueError("Unapproved upstream URL")
    with db.engine().begin() as conn:
        db.lock(conn, "fetch:" + key)
        old = conn.execute(select(db.cache).where(db.cache.c.key == key)).mappings().first()
        if old and old["next_at"] and old["next_at"] > now:
            return old["body"] if old["last_success_at"] else None
        # Lease is committed before the external request, preventing duplicate fetches.
        conn.execute(
            insert(db.cache)
            .values(
                key=key, body=old["body"] if old else {}, next_at=now + timedelta(seconds=120), failures=0
            )
            .on_conflict_do_update(index_elements=["key"], set_={"next_at": now + timedelta(seconds=120)})
        )
    if not reserve(provider, now, budget_limit):
        with db.engine().begin() as conn:
            conn.execute(update(db.cache).where(db.cache.c.key == key).values(error="BUDGET_DEFERRED"))
        return old["body"] if old else None
    headers = {
        "User-Agent": os.environ.get("LV_USER_AGENT", "launch-visibility/0.1 (local pilot)"),
        "Accept": "application/geo+json" if provider == "nws" else "application/json",
    }
    error, retry_s = None, period_s
    try:
        with (
            nullcontext(client)
            if client is not None
            else httpx.Client(timeout=20, follow_redirects=False) as transport
        ):
            with transport.stream("GET", url, headers=headers) as response:
                if response.status_code != 200:
                    error = "HTTP_" + str(response.status_code)
                    retry = response.headers.get("Retry-After")
                    if retry:
                        retry_s = max(
                            period_s,
                            int(retry)
                            if retry.isdigit()
                            else int((parsedate_to_datetime(retry) - now).total_seconds()),
                        )
                    raise ValueError(error)
                content = b""
                for chunk in response.iter_bytes():
                    content += chunk
                    if len(content) > 12_000_000:
                        raise ValueError("UPSTREAM_TOO_LARGE")
                payload = (
                    {"source_sha256": hashlib.sha256(content).hexdigest()}
                    if provider == "route"
                    else {"robots_text": content.decode("utf-8")}
                    if provider == "robots"
                    else json.loads(content)
                )
                if provider == "ll2" and not isinstance(payload.get("results"), list):
                    raise ValueError("UNSUPPORTED_PROVIDER_SCHEMA")
                if provider == "nws" and "properties" not in payload:
                    raise ValueError("UNSUPPORTED_PROVIDER_SCHEMA")
                cache_age = re.search(r"max-age=(\d+)", response.headers.get("Cache-Control", ""))
                if cache_age:
                    retry_s = max(retry_s, int(cache_age.group(1)))
        sha, path = atomic_snapshot(content)
        provenance = {
            "source_url": url,
            "sha256": sha,
            "fetched_at": stamp(now),
            "issued_at": payload.get("properties", {}).get("updateTime"),
            "source_revision": None,
            "license": "Original reviewed route source permission; content retained for validation only"
            if provider == "route"
            else "NWS US government data"
            if provider == "nws"
            else "The Space Devs LL2 attribution; no linked imagery redistributed",
            "parser_version": provider + "-v1",
            "kind": "provider",
            "notes": [],
        }
        result = {"payload": payload, "provenance": provenance}
        with db.engine().begin() as conn:
            conn.execute(
                insert(db.snapshots)
                .values(id=sha, sha256=sha, revision=1, body={**provenance, "path": path}, created_at=now)
                .on_conflict_do_nothing()
            )
            conn.execute(
                update(db.cache)
                .where(db.cache.c.key == key)
                .values(
                    body=result,
                    last_success_at=now,
                    failures=0,
                    error=None,
                    next_at=now + timedelta(seconds=retry_s),
                )
            )
        return result
    except (httpx.HTTPError, ValueError, OSError) as exc:
        failures = (old["failures"] if old else 0) + 1
        error = error or type(exc).__name__
        retry_s = max(retry_s, min(21600, 60 * 2 ** min(failures, 8)))
        if error == "HTTP_403":
            retry_s = max(retry_s, 86400)
        with db.engine().begin() as conn:
            conn.execute(
                update(db.cache)
                .where(db.cache.c.key == key)
                .values(failures=failures, error=error, next_at=now + timedelta(seconds=retry_s))
            )
        return old["body"] if old and old["last_success_at"] else None


def ingest_launches(result: dict, now: datetime) -> int:
    count = 0
    with db.engine().begin() as conn:
        db.lock(conn, "launch-ingestion")
        for raw in result["payload"]["results"]:
            if not ll2.supported_pad(raw.get("pad", {})):
                continue
            existing = (
                conn.execute(select(db.launches).where(db.launches.c.id == raw["id"]).with_for_update())
                .mappings()
                .first()
            )
            previous = existing["body"] if existing else None
            launch = ll2.normalize(raw, result["provenance"], previous)
            reviewed = conn.scalar(
                select(db.cache.c.body).where(db.cache.c.key == "reviewed-mission:" + launch["id"])
            )
            if reviewed and reviewed["source_updated_at"] == launch["source_updated_at"]:
                launch.update(reviewed["corrections"])

            def semantic(row):
                return {
                    k: v for k, v in row.items() if k not in ("provenance", "source_updated_at", "revision")
                }

            changed = previous is None or digest(semantic(previous)) != digest(semantic(launch))
            if existing and changed:
                launch["revision"] += 1
                conn.execute(
                    update(db.outbox)
                    .where(
                        db.outbox.c.launch_id == launch["id"],
                        db.outbox.c.state.in_(["pending", "claimed", "retry"]),
                    )
                    .values(state="cancelled")
                )
            vals = dict(
                id=launch["id"],
                revision=launch["revision"],
                body=launch,
                created_at=now,
                net=utc(launch["net"]) if launch["net"] else None,
                status=launch["status"],
                disabled=launch["disabled"],
            )
            conn.execute(
                insert(db.launches)
                .values(**vals)
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={k: v for k, v in vals.items() if k not in ("id", "created_at")},
                )
            )
            if changed:
                conn.execute(
                    db.revisions.insert().values(
                        id=str(uuid4()),
                        launch_id=launch["id"],
                        revision=launch["revision"],
                        body=launch,
                        created_at=now,
                    )
                )
                conn.execute(
                    insert(db.attempts)
                    .values(
                        id=launch["attempt_id"],
                        launch_id=launch["id"],
                        revision=1,
                        body={"launch_id": launch["id"]},
                        created_at=now,
                    )
                    .on_conflict_do_nothing()
                )
            count += 1
    return count


def weather_for(point: dict, now: datetime, near: bool = False) -> dict | None:
    coord = f"{point['latitude_deg']:.4f},{point['longitude_deg']:.4f}"
    result = fetch("https://api.weather.gov/points/" + coord, "point:" + coord, "nws", now, 86400)
    if not result:
        return None
    url = result["payload"]["properties"].get("forecastGridData", "")
    if not approved_url(url):
        return None
    result = fetch(url, url, "nws", now, 900 if near else 3600)
    if not result:
        return None
    try:
        return {
            "rows": nws.normalize(
                result["payload"], result["provenance"], url.rsplit("/", 2)[-2] + "/" + url.rsplit("/", 1)[-1]
            ),
            "provenance": result["provenance"],
        }
    except ValueError:
        return None


def schedule_page_url(next_url: str, previous_offset: int) -> tuple[str, int]:
    """Validate provider pagination without expanding the upstream host or source scope."""
    if not isinstance(next_url, str):
        raise ValueError("INVALID_SCHEDULE_NEXT")
    parsed = urlparse(next_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (
        not approved_url(next_url)
        or parsed.hostname != "ll.thespacedevs.com"
        or parsed.path != "/2.3.0/launches/upcoming/"
        or parsed.fragment
        or set(query) != {"limit", "location__ids", "offset"}
        or query["limit"] != ["100"]
        or query["location__ids"] != ["12,27"]
        or len(query["offset"]) != 1
        or not query["offset"][0].isascii()
        or not query["offset"][0].isdigit()
    ):
        raise ValueError("INVALID_SCHEDULE_NEXT")
    offset = int(query["offset"][0])
    if offset != previous_offset + 100:
        raise ValueError("NONSEQUENTIAL_SCHEDULE_NEXT")
    return LL2_URL + "&offset=" + str(offset), offset


def refresh_schedule(now: datetime, near: bool = False, client=None) -> dict:
    """Walk all pages; retain partial results and resume via cached pages after backoff.

    A broad page leaves the final hourly request slot for the imminent-launch page.
    No record is removed merely because a page refresh failed or a launch completed.
    """
    url, offset = LL2_URL, 0
    seen_ids: set[str] = set()
    status = {
        "checked_at": stamp(now),
        "scope": "Cape/Kennedy",
        "provider_count": None,
        "received": 0,
        "ingested": 0,
        "pages": 0,
        "complete": False,
        "error": None,
    }
    # An explicit operational bound guards malformed unending feeds; never claims completeness.
    for _ in range(100):
        key = "ll2" if offset == 0 else "ll2:page:" + str(offset)
        result = fetch(
            url,
            key,
            "ll2",
            now,
            300 if near and offset == 0 else 1800,
            client=client,
            budget_limit=12 if offset == 0 else 11,
        )
        with db.engine().connect() as conn:
            cached = conn.execute(select(db.cache).where(db.cache.c.key == key)).mappings().first()
        if result:
            page_ids = [row["id"] for row in result["payload"]["results"]]
            if len(set(page_ids)) != len(page_ids) or seen_ids.intersection(page_ids):
                status["error"] = "SCHEDULE_PAGE_OVERLAP"
                break
            seen_ids.update(page_ids)
            status["ingested"] += ingest_launches(result, now)
            status["received"] += len(result["payload"]["results"])
            status["pages"] += 1
            if offset == 0:
                status["provider_count"] = result["payload"].get("count")
        if not result or (cached and cached["error"]):
            status["error"] = cached["error"] if cached else "SCHEDULE_UNAVAILABLE"
            break
        next_url = result["payload"].get("next")
        if next_url is None:
            status["complete"] = status["provider_count"] == status["received"]
            if not status["complete"]:
                status["error"] = "SCHEDULE_COUNT_CHANGED"
            break
        try:
            url, offset = schedule_page_url(next_url, offset)
        except (ValueError, TypeError) as exc:
            status["error"] = str(exc) if isinstance(exc, ValueError) else "INVALID_SCHEDULE_NEXT"
            break
    else:
        status["error"] = "SCHEDULE_PAGE_LIMIT"
    with db.engine().begin() as conn:
        conn.execute(
            insert(db.cache)
            .values(key="ll2:catalog-status", body=status)
            .on_conflict_do_update(index_elements=["key"], set_={"body": status})
        )
    return status


def cycle(now: datetime) -> None:
    with db.engine().connect() as conn:
        near = bool(
            conn.scalar(
                select(func.count())
                .select_from(db.launches)
                .where(
                    db.launches.c.net >= now,
                    db.launches.c.net <= now + timedelta(hours=6),
                    db.launches.c.status == "scheduled",
                )
            )
        )
        points = (
            conn.execute(
                select(db.locations.c.body).where(db.locations.c.body["confirmed"].as_boolean().is_(True))
            )
            .scalars()
            .all()
        )
    refresh_schedule(now, near)
    refresh_routes(now)
    period = 900 if near else 3600
    for location in points[:100]:
        p = location["point"]
        cell = f"{p['latitude_deg']:.4f},{p['longitude_deg']:.4f}"
        slot = int(hashlib.sha256(cell.encode()).hexdigest()[:8], 16) % period
        with db.engine().connect() as conn:
            first_fetch = conn.scalar(select(db.cache.c.key).where(db.cache.c.key == "point:" + cell)) is None
        if first_fetch or (int(now.timestamp()) - slot) % period < 30:
            weather_for(p, now, near)


def refresh_routes(now: datetime) -> None:
    """Revalidate reviewed raw bytes. Changed documents require a new parser review."""
    with db.engine().connect() as conn:
        routes = conn.execute(select(db.routes.c.body)).scalars().all()
        launches = {launch["id"]: launch for launch in conn.execute(select(db.launches.c.body)).scalars()}
    for route in routes:
        launch = launches.get(route["launch_id"])
        if not launch or launch["status"] not in ("scheduled", "hold") or route["admission"] != "approved":
            continue
        url = route["provenance"][0]["source_url"]
        if not approved_url(url) or not url.startswith(
            ("https://www.nasa.gov/blogs/", "https://www.spacex.com/launches/")
        ):
            continue  # Other source formats/hosts need separately tested adapters.
        from urllib.robotparser import RobotFileParser

        robots_url = "https://" + urlparse(url).hostname + "/robots.txt"
        robots = fetch(robots_url, robots_url, "robots", now, 86400)
        policy = RobotFileParser()
        policy.parse(
            robots["payload"]["robots_text"].splitlines() if robots else ["User-agent: *", "Disallow: /"]
        )
        if not policy.can_fetch(os.environ.get("LV_USER_AGENT", "launch-visibility"), url):
            with db.engine().begin() as conn:
                conn.execute(
                    insert(db.cache)
                    .values(
                        key="route-check:" + route["id"],
                        body={},
                        failures=1,
                        error="ROBOTS_UNAVAILABLE_OR_DISALLOWED",
                        next_at=now + timedelta(days=1),
                    )
                    .on_conflict_do_update(
                        index_elements=["key"],
                        set_={
                            "error": "ROBOTS_UNAVAILABLE_OR_DISALLOWED",
                            "next_at": now + timedelta(days=1),
                        },
                    )
                )
            continue
        near = launch["net"] and (utc(launch["net"]) - now).total_seconds() <= 21600
        fetch(url, "route-check:" + route["id"], "route", now, 3600 if near else 21600)


if __name__ == "__main__":
    cycle(datetime.now(timezone.utc))
