"""Refresh the real scoped catalogue within worker budgets and record coverage gaps."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.api.config import load_env  # noqa: E402
from services.api import db  # noqa: E402
from services.worker.ingestion import refresh_schedule  # noqa: E402
from sqlalchemy import func, select  # noqa: E402


def main() -> int:
    load_env()
    at = datetime.now(timezone.utc)
    status = refresh_schedule(at)
    with db.engine().connect() as conn:
        counts = {
            table.name: conn.scalar(select(func.count()).select_from(table))
            for table in (db.launches, db.routes, db.profiles)
        }
        pages = (
            conn.execute(
                select(db.cache).where((db.cache.c.key == "ll2") | db.cache.c.key.startswith("ll2:page:"))
            )
            .mappings()
            .all()
        )
        provenance = [
            {"key": row["key"], "error": row["error"], "provenance": row["body"].get("provenance")}
            for row in pages
        ]
    report = {
        "at": at.isoformat(),
        "catalog": status,
        "stored_counts": counts,
        "sources": provenance,
        "visibility_integration_complete": False,
        "missing_implementation": "Automatic per-mission route discovery and qualified ascent profiles",
        "simulation_scope": "Authored Dragon/station family scenario only; not an API trajectory",
    }
    target = ROOT / "evidence/build/source-audit/catalog.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if status["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
