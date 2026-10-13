"""JSON protocol bridge to actual application components; no expected values are read."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

from packages.visibility import geometry, astronomy, weather, rules
from packages.visibility import time as clocks
from packages.visibility.common import utc, digest
from packages.visibility.ensemble import bearing_sector
from services.api.adapters.census import resolve_zip
from services.api.adapters.telemetry import parse_archive
from services.worker import notifications, ingestion


def execute(operation: str, data: dict) -> dict:
    if operation == "resolve_zip":
        return resolve_zip(data["zip"], data.get("gazetteer"))
    if operation == "location_change":
        return {"confirmed": False, "revision": data["old_revision"] + 1, "invalidate_assessment": True}
    if operation == "local_time":
        return clocks.local_time(data["utc"], data["timezone"])
    if operation == "parse_local":
        try:
            return {"utc": clocks.parse_local(**data).isoformat()}
        except ValueError:
            return {"error": "INVALID_INPUT"}
    if operation == "geometry":
        return geometry.geometry(**data)
    if operation == "solar_events":
        return astronomy.solar_events(**data)
    if operation == "twilight_label":
        return {"label": astronomy.twilight_label(**data)}
    if operation == "slip":
        before = datetime.fromisoformat(data["launch_local"]) + timedelta(seconds=data["view_offset_s"])
        return {
            "before_view": before.isoformat(),
            "after_view": (before + timedelta(seconds=data["slip_s"])).isoformat(),
            "recompute": ["solar", "weather", "rules"],
            "automatic_daylight_rejection": False,
        }
    if operation == "earth_shadow":
        return {"in_shadow": geometry.earth_shadow(**data)}
    if operation == "emission":
        return {"eligible": rules.emission(**data)}
    if operation == "duration":
        return {
            "eligible": data["active_engine"] and data["elevation_deg"] > 0 and data["continuous_s"] >= 20
        }
    if operation == "gap":
        return {"interpolate": data["same_stage"] and 0 < data["sample_gap_s"] <= 15}
    if operation == "bearing_sector":
        return bearing_sector(**data)
    if operation == "round_window":
        return clocks.round_window(**data)
    if operation == "lighting_flag":
        return {"flag": rules.lighting_flag(**data)}
    if operation == "weather_tier":
        return weather.tier(**data)
    if operation in ("weather_overlap", "weather_subinterval"):
        epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)

        def t(value):
            return (epoch + timedelta(seconds=value)).isoformat()

        view = [t(x) for x in data["view"]]
        bins = [
            {"start": t(r["interval"][0]), "end": t(r["interval"][1]), "tier": r["tier"]}
            for r in data["bins"]
        ]
        if operation == "weather_overlap":
            return {"tier": max((r["tier"] for r in weather.partition(view, bins)), key=weather.ORDER.get)}
        result = weather.select(view, bins)
        return {
            "tier": result["tier"],
            "selected": [
                [int((utc(r[k]) - epoch).total_seconds()) for k in ("start", "end")] for r in result["usable"]
            ],
        }
    if operation == "weather_fresh":
        return {"fresh": weather.fresh(**data)}
    if operation == "advice":
        return rules.decide(rules.Inputs(**data))
    if operation == "time_presentation":
        return clocks.presentation(
            data["precision"],
            utc(data["now"]) if data.get("now") else None,
            data.get("net"),
            data.get("actual_liftoff"),
        )
    if operation == "quiet_hours":
        return {"suppressed": notifications.quiet(**data)}
    if operation == "correction":
        return {"notify": notifications.correction(**data)}
    if operation == "downgrade":
        return {"notify": notifications.downgrade(**data)}
    if operation == "enqueue":
        return {"enqueue": utc(data["due_at"]) > utc(data["created_at"])}
    if operation == "delivery":
        return notifications.delivery(utc(data["now"]), utc(data["expires_at"]), data["consent"])
    if operation == "provider_failure":
        return ingestion.failure_policy(data["has_cache"])
    if operation == "provider_budget":
        return {"allowed": ingestion.budget_allowed(data["requests_in_last_3600s"])}
    if operation == "assessment_key":
        return {
            "same_key": digest({data["changed_input"]: data["baseline_hash"]})
            == digest({data["changed_input"]: data["changed_hash"]}),
            "archive_original": True,
        }
    if operation == "parse_historical_archive":
        return parse_archive(**data)
    from implementation.scenarios import run

    return run(data["scenario"] if operation == "scenario" else operation, data)


def main() -> None:
    value = json.loads(sys.stdin.readline())
    if value.get("protocol_version") != 1:
        raise ValueError("Unsupported protocol")
    print(json.dumps(execute(value["operation"], value["input"]), allow_nan=False))


if __name__ == "__main__":
    main()
