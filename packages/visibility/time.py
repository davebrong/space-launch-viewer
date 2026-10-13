from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections.abc import Callable, Iterable

from .common import utc, stamp


def local_time(value: str | datetime, timezone: str) -> dict:
    d = utc(value).astimezone(ZoneInfo(timezone))
    return {"local": d.isoformat(), "abbreviation": d.tzname(), "fold": d.fold}


def parse_local(local: str, timezone: str, offset: str | None = None) -> datetime:
    naive = datetime.fromisoformat(local)
    if naive.tzinfo is not None:
        raise ValueError("Local input must carry its offset separately")
    zone = ZoneInfo(timezone)
    choices = {}
    for fold in (0, 1):
        candidate = naive.replace(tzinfo=zone, fold=fold)
        back = utc(candidate).astimezone(zone)
        if back.replace(tzinfo=None) == naive:
            choices[candidate.isoformat()[-6:]] = candidate
    if not choices or (len(choices) > 1 and offset is None):
        raise ValueError("Nonexistent or ambiguous local time")
    if offset is not None and offset not in choices:
        raise ValueError("Invalid offset for observer zone")
    return utc(choices[offset] if offset else next(iter(choices.values())))


def presentation(
    precision: str,
    now: datetime | None = None,
    net: str | None = None,
    actual_liftoff: str | None = None,
    status: str = "scheduled",
    fresh: bool = True,
) -> dict:
    display = "forecast" if status == "scheduled" else status
    if status == "scheduled" and now and net and utc(now) >= utc(net) and not actual_liftoff:
        display = "awaiting_confirmation"
    return {
        "display_status": display,
        "countdown": precision == "exact" and display == "forecast" and fresh,
        "conditional": precision == "window",
        "precise_reminder": precision == "exact" and display == "forecast" and fresh,
    }


def round_window(start: str, end: str) -> dict:
    a, b = utc(start), utc(end)
    if b <= a:
        raise ValueError("Positive interval required")
    a = a.replace(second=0, microsecond=0)
    b = b if not (b.second or b.microsecond) else b.replace(second=0, microsecond=0) + timedelta(minutes=1)
    return {"start": stamp(a), "end": stamp(b)}


def alternatives(
    start: datetime, end: datetime, evaluate: Callable, transitions: Iterable[datetime] = ()
) -> list:
    start, end = utc(start), utc(end)
    if end < start or end - start > timedelta(hours=48):
        raise ValueError("time_insufficient")
    points = {start, end, *(utc(t) for t in transitions if start <= utc(t) <= end)}
    t = start
    while t < end:
        points.add(t)
        t += timedelta(minutes=5)
    results = {t: evaluate(t) for t in sorted(points)}
    pending = list(zip(sorted(points), sorted(points)[1:]))
    while pending:
        a, b = pending.pop()
        if results[a] != results[b] and (b - a).total_seconds() > 60:
            mid = a + (b - a) / 2
            results[mid] = evaluate(mid)
            pending.extend(((a, mid), (mid, b)))
    return [{"t0": stamp(t), "result": results[t]} for t in sorted(results)]
