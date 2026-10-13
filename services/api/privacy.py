"""Remove orphaned point lookups, including GPS-bearing provider snapshots."""

from sqlalchemy import select, delete
from . import db
from .config import DATA


def purge_points(conn, removed: list[dict]) -> None:
    remaining = {
        f"{x['point']['latitude_deg']:.4f},{x['point']['longitude_deg']:.4f}"
        for x in conn.execute(select(db.locations.c.body)).scalars()
    }
    for loc in removed:
        p = loc["point"]
        coord = f"{p['latitude_deg']:.4f},{p['longitude_deg']:.4f}"
        if coord in remaining:
            continue
        conn.execute(delete(db.cache).where(db.cache.c.key == "point:" + coord))
        snapshots = (
            conn.execute(
                select(db.snapshots).where(
                    db.snapshots.c.body["source_url"].as_string() == "https://api.weather.gov/points/" + coord
                )
            )
            .mappings()
            .all()
        )
        for row in snapshots:
            target = (DATA / "snapshots" / (row["sha256"] + ".json")).resolve()
            if target.is_relative_to((DATA / "snapshots").resolve()):
                target.unlink(missing_ok=True)
            conn.execute(delete(db.snapshots).where(db.snapshots.c.id == row["id"]))
