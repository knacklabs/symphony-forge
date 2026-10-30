"""Time-ordered ids and database-owned update times."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_ids_and_updated_at"
down_revision: str | None = "0006_extensions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

ID_TABLES = (
    "account",
    "session",
    "password_reset_token",
    "organisation",
    "membership",
    "invite",
    "project",
    "change_record",
)
UPDATED_TABLES = ("account", "organisation", "membership", "invite", "project")


def upgrade() -> None:
    for table in ID_TABLES:
        op.alter_column(table, "id", server_default=sa.text("uuidv7()"))
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at_utc = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$;
        """
    )
    for table in UPDATED_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_set_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )


def downgrade() -> None:
    for table in reversed(UPDATED_TABLES):
        op.execute(f"DROP TRIGGER {table}_set_updated_at ON {table}")
    op.execute("DROP FUNCTION set_updated_at()")
    for table in reversed(ID_TABLES):
        op.alter_column(table, "id", server_default=None)
