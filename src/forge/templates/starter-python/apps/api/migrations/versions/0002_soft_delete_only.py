"""Refuse hard deletes of projects."""

from collections.abc import Sequence

from alembic import op

revision: str = "0002_soft_delete_only"
down_revision: str | None = "0001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION soft_delete_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Records are soft deleted. Set the deleted timestamp instead.';
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER soft_delete_only
        BEFORE DELETE ON project
        FOR EACH ROW EXECUTE FUNCTION soft_delete_only();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER soft_delete_only ON project")
    op.execute("DROP FUNCTION soft_delete_only()")
