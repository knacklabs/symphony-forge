"""Use text columns with named checks instead of varchar and native enums."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_columns"
down_revision: str | None = "0008_module_schemas"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TEXT_COLUMNS = (
    ("core", "account", (("email", 254), ("password_hash", 255))),
    ("core", "session", (("token_hash", 64), ("csrf_token_hash", 64))),
    ("core", "password_reset_token", (("token_hash", 64),)),
    ("core", "membership", (("email", 254),)),
    ("core", "invite", (("email", 254), ("token_hash", 64))),
    ("projects", "project", (("name", 120),)),
    (
        "history",
        "change_record",
        (("actor_email", 254), ("action", 40), ("summary", 400)),
    ),
)
ENUM_COLUMNS = (
    ("projects", "project", "status", "project_status", ("active", "archived")),
    ("core", "membership", "role", "membership_role", ("admin", "member")),
)
CHECKS = (
    (
        "projects",
        "project",
        "project_status_allowed",
        "status IN ('active', 'archived')",
    ),
    ("core", "membership", "membership_role_allowed", "role IN ('admin', 'member')"),
    (
        "projects",
        "project",
        "project_name_length",
        "char_length(name) BETWEEN 1 AND 120",
    ),
    ("core", "account", "account_email_lower", "email = lower(email)"),
    ("core", "invite", "invite_email_lower", "email = lower(email)"),
)


def upgrade() -> None:
    for schema, table, columns in TEXT_COLUMNS:
        for column, length in columns:
            op.alter_column(
                table,
                column,
                schema=schema,
                existing_type=sa.String(length),
                type_=sa.Text(),
            )
    for schema, table, column, enum, values in ENUM_COLUMNS:
        op.alter_column(
            table,
            column,
            schema=schema,
            existing_type=postgresql.ENUM(*values, name=enum, schema=schema),
            type_=sa.Text(),
            postgresql_using=f"{column}::text",
        )
    for schema, table, name, condition in CHECKS:
        op.create_check_constraint(name, table, condition, schema=schema)
    for schema, _, _, enum, _ in ENUM_COLUMNS:
        op.execute(f"DROP TYPE {schema}.{enum}")


def downgrade() -> None:
    for schema, table, name, _ in reversed(CHECKS):
        op.drop_constraint(name, table, schema=schema, type_="check")
    for schema, table, column, enum, values in ENUM_COLUMNS:
        native_enum = postgresql.ENUM(*values, name=enum, schema=schema)
        native_enum.create(op.get_bind())
        op.alter_column(
            table,
            column,
            schema=schema,
            existing_type=sa.Text(),
            type_=native_enum,
            postgresql_using=f"{column}::{schema}.{enum}",
        )
    for schema, table, columns in TEXT_COLUMNS:
        for column, length in columns:
            op.alter_column(
                table,
                column,
                schema=schema,
                existing_type=sa.Text(),
                type_=sa.String(length),
            )
