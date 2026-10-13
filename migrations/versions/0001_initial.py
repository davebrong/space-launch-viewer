"""Initial schema. Downgrade is intentionally restore-only to preserve immutable evidence."""
from alembic import op
from services.api.db import metadata

revision = "0001"
down_revision = None


def upgrade() -> None:
    metadata.create_all(op.get_bind())
    op.execute("""
    CREATE FUNCTION reject_immutable_update() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'immutable evidence cannot be updated'; END $$;
    """)
    for table in ("provider_snapshots", "launch_revisions", "assessments", "admin_audit"):
        op.execute(f"CREATE TRIGGER immutable_update BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_immutable_update()")


def downgrade() -> None:
    raise RuntimeError("Restore a verified prior backup; destructive downgrade is not supported")
