"""Compare real catalog responses for two ZIPs using a disposable local API session."""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from services.api.config import ORIGIN

    results = {}
    with httpx.Client(base_url=ORIGIN + "/api/v1", timeout=60, headers={"Origin": ORIGIN}) as client:
        session = client.post("/session")
        session.raise_for_status()
        client.headers["X-CSRF-Token"] = session.headers["X-CSRF-Token"]
        try:

            def all_rows(path):
                rows, cursor = [], None
                while True:
                    response = client.get(
                        path, params={"limit": 100, **({"cursor": cursor} if cursor else {})}
                    )
                    response.raise_for_status()
                    rows.extend(response.json())
                    cursor = response.headers.get("X-Next-Cursor")
                    if not cursor:
                        return rows

            launches = {r["id"]: r for r in all_rows("/launches")}
            for zip_code in ("32801", "21201"):
                response = client.post(
                    "/locations/resolve",
                    json={"zip": zip_code, "latitude_deg": None, "longitude_deg": None, "altitude_m": None},
                )
                response.raise_for_status()
                loc = response.json()
                response = client.post(
                    f"/locations/{loc['id']}/confirm", json={"revision": loc["revision"], "confirmed": True}
                )
                response.raise_for_status()
                rows = all_rows(f"/locations/{loc['id']}/viewing-opportunities")
                results[zip_code] = [
                    {
                        **r,
                        "name": launches[r["launch_id"]]["name"],
                        "net": launches[r["launch_id"]]["net"],
                        "time_precision": launches[r["launch_id"]]["time_precision"],
                    }
                    for r in rows
                    if r["viewable"]
                ]
            nearby_ids = {r["launch_id"] for r in results["32801"]}
            distant_ids = {r["launch_id"] for r in results["21201"]}
            bandwagon = "3b430f81-0ff1-4d85-8a1a-cef0de326198"
            assert bandwagon in nearby_ids and bandwagon not in distant_ids
        finally:
            client.delete("/privacy").raise_for_status()
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "catalog_count": len(launches),
        "results": results,
        "test_session_deleted": True,
    }
    (ROOT / "evidence/build/nearby-live.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
