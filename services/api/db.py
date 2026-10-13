from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import (
    MetaData,
    Table,
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB


metadata = MetaData()
sessions = Table(
    "owner_sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("capability_hash", String, unique=True, nullable=False),
    Column("csrf_hash", String, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
)


def document(name: str, private: bool = False, *extra) -> Table:
    cols = [
        Column("id", String, primary_key=True),
        Column("revision", Integer, nullable=False, default=1),
        Column("body", JSONB, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False),
    ]
    if private:
        cols.append(
            Column(
                "owner_id",
                String,
                ForeignKey("owner_sessions.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            )
        )
    return Table(name, metadata, *cols, *extra, CheckConstraint("revision >= 1"))


locations = document(
    "locations",
    True,
    Column("expires_at", DateTime(timezone=True)),
    Column("canonical", String),
    UniqueConstraint("owner_id", "canonical"),
)
launches = document(
    "launches",
    False,
    Column("net", DateTime(timezone=True), index=True),
    Column("status", String, nullable=False),
    Column("disabled", Boolean, nullable=False, default=False),
)
revisions = document(
    "launch_revisions",
    False,
    Column("launch_id", String, ForeignKey("launches.id"), nullable=False),
    UniqueConstraint("launch_id", "revision"),
)
attempts = document("attempts", False, Column("launch_id", String, ForeignKey("launches.id"), nullable=False))
snapshots = document("provider_snapshots", False, Column("sha256", String, unique=True, nullable=False))
routes = document("route_evidence")
profiles = document("profile_versions")
associations = document("associations")
weather = document(
    "weather_intervals",
    False,
    Column("grid_id", String, index=True),
    Column("start_at", DateTime(timezone=True)),
    Column("end_at", DateTime(timezone=True)),
    CheckConstraint("end_at > start_at"),
)
assessments = document(
    "assessments",
    True,
    Column("input_digest", String, nullable=False, unique=True),
    Column("launch_id", String, ForeignKey("launches.id"), nullable=False, index=True),
    Column("location_id", String, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False, index=True),
)
subscriptions = document(
    "subscriptions",
    True,
    Column("location_id", String, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False),
    Column("enabled", Boolean, nullable=False, default=True),
    Column("unsubscribe_hash", String, unique=True, nullable=False),
)
jobs = document(
    "scheduled_jobs",
    False,
    Column("job_key", String, nullable=False, unique=True),
    Column("due_at", DateTime(timezone=True), nullable=False),
    Column("lease_until", DateTime(timezone=True)),
    Column("state", String, nullable=False, default="pending"),
    Column("attempts", Integer, nullable=False, default=0),
)
outbox = document(
    "outbox",
    True,
    Column(
        "subscription_id",
        String,
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("launch_id", String, ForeignKey("launches.id"), nullable=False),
    Column("assessment_id", String, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
    Column("dedupe_key", String, unique=True, nullable=False),
    Column("state", String, nullable=False),
    Column("due_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("lease_until", DateTime(timezone=True)),
    CheckConstraint("expires_at > due_at"),
)
notices = document(
    "notifications",
    True,
    Column("outbox_id", String, ForeignKey("outbox.id", ondelete="CASCADE"), unique=True, nullable=False),
)
observations = document(
    "observations",
    True,
    Column("assessment_id", String, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
)
audit = document("admin_audit")
ledger = Table(
    "deletion_ledger",
    metadata,
    Column("id", String, primary_key=True),
    Column("deleted_at", DateTime(timezone=True), nullable=False),
)
budget = Table(
    "provider_budget",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("provider", String, nullable=False, index=True),
    Column("requested_at", DateTime(timezone=True), nullable=False),
)
cache = Table(
    "provider_cache",
    metadata,
    Column("key", String, primary_key=True),
    Column("body", JSONB, nullable=False),
    Column("last_success_at", DateTime(timezone=True)),
    Column("next_at", DateTime(timezone=True)),
    Column("failures", Integer, nullable=False, default=0),
    Column("error", String),
)
idempotency = Table(
    "idempotency",
    metadata,
    Column("owner_id", String, ForeignKey("owner_sessions.id", ondelete="CASCADE"), primary_key=True),
    Column("key", String, primary_key=True),
    Column("request_hash", String, nullable=False),
    Column("body", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
Index("jobs_due", jobs.c.state, jobs.c.due_at)
Index("outbox_due", outbox.c.state, outbox.c.due_at)


@lru_cache(maxsize=1)
def engine():
    url = os.environ.get("DATABASE_URL")
    if not url or not url.startswith("postgresql+psycopg://"):
        raise RuntimeError("Configure PostgreSQL DATABASE_URL; no in-memory production fallback")
    return create_engine(url, pool_pre_ping=True, pool_size=10, max_overflow=15)


def lock(conn, key: str) -> None:
    conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})
