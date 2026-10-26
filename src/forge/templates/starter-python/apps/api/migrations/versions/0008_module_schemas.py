"""Keep each module's tables and enums in its own Postgres schema."""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_module_schemas"
down_revision: str | None = "0007_ids_and_updated_at"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLES = {
    "core": (
        "account",
        "session",
        "password_reset_token",
        "organisation",
        "membership",
        "invite",
    ),
    "history": ("change_record",),
    "projects": ("project",),
}
ENUMS = {"core": "membership_role", "projects": "project_status"}


def upgrade() -> None:
    for schema, tables in TABLES.items():
        op.execute(f"CREATE SCHEMA {schema}")
        for table in tables:
            op.execute(f"ALTER TABLE public.{table} SET SCHEMA {schema}")
    for schema, enum in ENUMS.items():
        op.execute(f"ALTER TYPE public.{enum} SET SCHEMA {schema}")


def downgrade() -> None:
    for schema, enum in ENUMS.items():
        op.execute(f"ALTER TYPE {schema}.{enum} SET SCHEMA public")
    for schema, tables in reversed(TABLES.items()):
        for table in reversed(tables):
            op.execute(f"ALTER TABLE {schema}.{table} SET SCHEMA public")
        op.execute(f"DROP SCHEMA {schema}")
