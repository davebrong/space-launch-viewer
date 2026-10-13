from __future__ import annotations

from collections import Counter
from sqlalchemy import select
from . import db
from packages.visibility.common import utc


def coverage(conn) -> dict:
    launch_rows = conn.execute(select(db.launches.c.body)).scalars().all()
    launches = [launch["id"] for launch in launch_rows]
    launch_times = {launch["id"]: launch["actual_liftoff"] or launch["net"] for launch in launch_rows}
    assessments = conn.execute(select(db.assessments.c.body)).scalars().all()
    observations = conn.execute(select(db.observations.c.body)).scalars().all()
    supported = {a["launch_id"] for a in assessments if a["mode"] in ("reconstructed", "official_guidance")}
    counts = Counter(o["outcome"] for o in observations)
    forecasts = {a["id"]: a for a in assessments}

    def positive(a):
        return a["advice"] in ("Possible", "Worth a look")

    def prospective(o):
        forecast = forecasts[o["assessment_id"]]
        launch_at = launch_times.get(o["launch_id"])
        return (
            not o.get("retrospective", False)
            and launch_at is not None
            and utc(forecast["computed_at"]) < utc(launch_at) <= utc(o["observed_at"])
        )

    labeled = [o for o in observations if o["outcome"] in ("seen", "not_seen") and prospective(o)]
    return {
        "all_cape_missions": len(launches),
        "supported_missions": len(supported),
        "unsupported_missions": len(set(launches) - supported),
        "outcomes": {k: counts[k] for k in ("seen", "not_seen", "inconclusive", "not_attempted")},
        "false_positive_attempts": sum(
            o["outcome"] == "not_seen" and positive(forecasts[o["assessment_id"]]) for o in labeled
        ),
        "missed_sighting_attempts": sum(
            o["outcome"] == "seen" and not positive(forecasts[o["assessment_id"]]) for o in labeled
        ),
        "labeled_denominator": len(labeled),
        "retrospective_reports": sum(not prospective(o) for o in observations),
        "launches_with_observations": len({o["launch_id"] for o in observations}),
        "missing_feedback_counted_as_negative": False,
        "reconstruction_cap": "Possible",
        "limitations": [
            "Self-reported outcomes; no feedback is not a negative.",
            "Retrospective reports are excluded from forecast validation and labeled pilot denominators.",
            "Prospective archives and forecast-time weather must be reviewed before pilot admission.",
        ],
    }
