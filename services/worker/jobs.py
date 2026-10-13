from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import select, update, or_, and_
from sqlalchemy.dialects.postgresql import insert

from services.api import db


def schedule(key: str, body: dict, at: datetime) -> None:
    with db.engine().begin() as conn:
        conn.execute(
            insert(db.jobs)
            .values(
                id=str(uuid4()),
                revision=1,
                body=body,
                created_at=at,
                job_key=key,
                due_at=at,
                state="pending",
                attempts=0,
            )
            .on_conflict_do_nothing(index_elements=["job_key"])
        )


def claim(at: datetime) -> dict | None:
    with db.engine().begin() as conn:
        row = (
            conn.execute(
                select(db.jobs)
                .where(
                    db.jobs.c.due_at <= at,
                    or_(
                        db.jobs.c.state.in_(["pending", "retry"]),
                        and_(db.jobs.c.state == "claimed", db.jobs.c.lease_until <= at),
                    ),
                )
                .order_by(db.jobs.c.due_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            .mappings()
            .first()
        )
        if not row:
            return None
        conn.execute(
            update(db.jobs)
            .where(db.jobs.c.id == row["id"])
            .values(state="claimed", lease_until=at + timedelta(seconds=120), attempts=row["attempts"] + 1)
        )
        return dict(row)


def complete(id: str) -> None:
    with db.engine().begin() as conn:
        conn.execute(update(db.jobs).where(db.jobs.c.id == id).values(state="completed", lease_until=None))


def retry(id: str, at: datetime) -> None:
    with db.engine().begin() as conn:
        row = conn.execute(select(db.jobs).where(db.jobs.c.id == id).with_for_update()).mappings().one()
        conn.execute(
            update(db.jobs)
            .where(db.jobs.c.id == id)
            .values(
                state="failed" if row["attempts"] >= 5 else "retry",
                lease_until=None,
                due_at=at + timedelta(seconds=min(900, 60 * 2 ** max(0, row["attempts"] - 1))),
            )
        )
