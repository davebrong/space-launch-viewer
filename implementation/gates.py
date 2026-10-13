"""External evidence gates. An unsupported result is never a passed real-data gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone

import httpx

from services.api.config import ROOT
from services.api.adapters.telemetry import parse_archive
from packages.visibility.common import stamp


def record(gate: str, report: dict) -> None:
    folder = ROOT / "evidence/build"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (gate + ".json")
    path.write_text(json.dumps(report, indent=2))
    gates_path = ROOT / "evidence/gates.json"
    gates = json.loads(gates_path.read_text())
    for row in gates:
        if row["id"] == gate:
            row.update(
                status=report["status"],
                reason=report["reason"],
                evidence=str(path.relative_to(ROOT)),
                attempted_at=report["run_at"],
            )
    gates_path.write_text(json.dumps(gates, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def historical() -> dict:
    now = datetime.now(timezone.utc)
    base = ROOT / "tests/fixtures/raw"
    parsed = parse_archive(
        base / "Telemetry-Data--Orbcomm OG2--JSON--analysed.json",
        base / "Telemetry-Data--Orbcomm OG2--JSON--events.json",
    )
    parsed.pop("samples")
    report = {
        "run_at": stamp(now),
        "status": "blocked",
        "parser_result": parsed,
        "reason": "Orbcomm OG2 has no independently verified geodetic route, altitude datum/stage admission or different held-out qualified profile. No Maryland estimate is asserted.",
        "missing_inputs": [
            "independent historical mission route",
            "verified profile altitude datum and stage identity",
            "held-out compatible mission",
        ],
        "retrievals": [],
    }
    urls = [
        "https://raw.githubusercontent.com/shahar603/Telemetry-Data/b245d3b81aa36b7941ec10f3f4b508999d106a6d/Orbcomm%20OG2/README.md",
        "https://raw.githubusercontent.com/shahar603/Telemetry-Data/b245d3b81aa36b7941ec10f3f4b508999d106a6d/LICENSE",
    ]
    for url in urls:
        try:
            r = httpx.get(url, timeout=20, follow_redirects=False)
            sha = hashlib.sha256(r.content).hexdigest()
            (ROOT / "evidence/build" / (sha + ".txt")).write_bytes(r.content)
            report["retrievals"].append(
                {"url": url, "status": r.status_code, "at": stamp(now), "sha256": sha}
            )
        except httpx.HTTPError as exc:
            report["retrievals"].append({"url": url, "status": type(exc).__name__, "at": stamp(now)})
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gate", choices=["historical-cape", "upcoming-cape", "official-guidance", "pilot"])
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.gate == "historical-cape":
        report, gate = historical(), "G-REAL"
    elif args.gate == "upcoming-cape":
        from services.worker.ingestion import fetch, ingest_launches, LL2_URL, weather_for
        from services.api.adapters.ll2 import supported_pad

        result = fetch(LL2_URL, "ll2", "ll2", now, 1800)
        missions = (
            [r for r in result["payload"]["results"] if supported_pad(r.get("pad", {}))] if result else []
        )
        if result:
            ingest_launches(result, now)
        weather = weather_for({"latitude_deg": 39.0, "longitude_deg": -77.0}, now)
        report = {
            "run_at": stamp(now),
            "status": "blocked",
            "reason": "Upcoming Cape schedule attempted; no approved mission-specific path and compatible profile in registry. Timed visibility remains unavailable.",
            "url": LL2_URL,
            "provider_received": bool(result),
            "missions": [{"id": m["id"], "name": m["name"], "net": m["net"]} for m in missions],
            "schedule_provenance": result["provenance"] if result else None,
            "weather_provenance": weather["provenance"] if weather else None,
            "weather_bins": len(weather["rows"]) if weather else 0,
            "next_action": "Admit a mission-specific independently sourced published path plus compatible profile; hazard areas cannot supply it.",
        }
        gate = "G-UPCOMING"
    elif args.gate == "official-guidance":
        url = "https://www.nasa.gov/blogs/wallops/2025/08/26/nasa-sounding-rocket-mission-targeting-aug-26-launch-attempt/"
        try:
            r = httpx.get(url, timeout=20, follow_redirects=False)
            status = r.status_code
            sha = hashlib.sha256(r.content).hexdigest()
            (ROOT / "evidence/build/nasa-tomex.html").write_bytes(r.content)
        except httpx.HTTPError as exc:
            status, sha = type(exc).__name__, None
        report = {
            "run_at": stamp(now),
            "status": "blocked",
            "reason": "NASA TOMEX+ guidance retrieved for review. No verified coordinate membership and observer-specific usable interval fixture is yet admitted; launch window alone is insufficient.",
            "url": url,
            "http_status": status,
            "sha256": sha,
        }
        gate = "G-GUIDANCE"
    else:
        report = {
            "run_at": stamp(now),
            "status": "blocked",
            "reason": "Prospective human observations for five launches and thirty labeled attempts have not been collected. Software fixtures do not count.",
        }
        gate = "G-PILOT"
    record(gate, report)
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
