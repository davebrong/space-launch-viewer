"""Protect reviewed registry versions and observations from in-place edits."""
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    for table in ("route_evidence", "profile_versions", "observations"):
        op.execute(f"CREATE TRIGGER immutable_update BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_immutable_update()")


def downgrade() -> None:
    raise RuntimeError("Restore a verified prior backup")
