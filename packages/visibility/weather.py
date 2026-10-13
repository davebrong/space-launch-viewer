from __future__ import annotations

from .common import utc, stamp, finite

ORDER = {"clear": 0, "mixed": 1, "poor": 2, "stale": 3, "unavailable": 4}


def tier(
    total: float | None,
    visibility_m: float | None = None,
    fog: bool | None = None,
    low: float | None = None,
    mid: float | None = None,
    high: float | None = None,
) -> dict:
    values = [x for x in (total, low, mid, high) if x is not None]
    finite(*values)
    if any(not 0 <= x <= 100 for x in values):
        raise ValueError("Cloud percent outside 0..100")
    if visibility_m is not None:
        finite(visibility_m)
        if visibility_m < 0:
            raise ValueError("Negative visibility")
    result = "mixed"
    if total is None:
        result = "unavailable"
    elif (
        total >= 75
        or (low is not None and low >= 60)
        or (visibility_m is not None and visibility_m < 5000)
        or fog is True
    ):
        result = "poor"
    elif (
        total <= 25
        and all(v is None or v <= limit for v, limit in ((low, 20), (mid, 40), (high, 60)))
        and (visibility_m is None or visibility_m >= 10000)
    ):
        result = "clear"
    return {"tier": result, "visibility_unknown": visibility_m is None}


def fresh(fetch_age_s: float, issue_age_s: float | None, covered: bool) -> bool:
    return bool(
        covered and -300 <= fetch_age_s <= 3600 and issue_age_s is not None and -300 <= issue_age_s <= 43200
    )


def partition(view: list | dict, bins: list[dict]) -> list[dict]:
    a, b = (utc(view[k]) for k in ("start", "end")) if isinstance(view, dict) else map(utc, view)
    if b <= a:
        raise ValueError("Invalid viewing interval")
    normalized = []
    edges = {a, b}
    for row in bins:
        start, end = utc(row["start"]), utc(row["end"])
        if end <= start:
            raise ValueError("Invalid weather interval")
        if start < b and end > a:
            normalized.append(
                (
                    start,
                    end,
                    row.get("tier")
                    or tier(row.get("total"), row.get("visibility_m"), row.get("fog"))["tier"],
                )
            )
            edges.update((max(a, start), min(b, end)))
    edges = sorted(edges)
    parts = []
    for start, end in zip(edges, edges[1:]):
        overlapping = [t for x, y, t in normalized if x < end and y > start]
        worst = max(overlapping, key=ORDER.get) if overlapping else "unavailable"
        if parts and parts[-1]["tier"] == worst:
            parts[-1]["end"] = stamp(end)
        else:
            parts.append({"start": stamp(start), "end": stamp(end), "tier": worst})
    return parts


def select(view: list | dict, bins: list[dict]) -> dict:
    parts = partition(view, bins)
    usable = []
    for row in parts:
        if row["tier"] in ("clear", "mixed"):
            if usable and usable[-1]["end"] == row["start"]:
                usable[-1]["end"] = row["end"]
                usable[-1]["tier"] = max((usable[-1]["tier"], row["tier"]), key=ORDER.get)
            else:
                usable.append(dict(row))
    usable = [r for r in usable if (utc(r["end"]) - utc(r["start"])).total_seconds() >= 20]
    clear = [
        r for r in parts if r["tier"] == "clear" and (utc(r["end"]) - utc(r["start"])).total_seconds() >= 20
    ]
    chosen = clear or usable
    result = (
        min((r["tier"] for r in chosen), key=ORDER.get)
        if chosen
        else max((r["tier"] for r in parts), key=ORDER.get)
    )
    if not chosen and result in ("clear", "mixed"):
        result = "poor"
    return {
        "tier": result,
        "parts": parts,
        "usable": chosen,
        "selected": [chosen[0]["start"], chosen[0]["end"]] if chosen else None,
        "narrowed": len(parts) != 1 or any(r["tier"] in ("unavailable", "poor") for r in parts),
    }
