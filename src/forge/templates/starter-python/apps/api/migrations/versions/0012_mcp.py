"""Transactional keys for safe agent create retries."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_mcp"
down_revision: str | None = "0011_agents"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA mcp")
    op.create_table(
        "idempotency_key",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("uuidv7()"), primary_key=True
        ),
        sa.Column(
            "organisation_id",
            sa.Uuid(),
            sa.ForeignKey(
                "core.organisation.id",
                ondelete="RESTRICT",
                name="idempotency_key_organisation_id_fkey",
            ),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            sa.Uuid(),
            sa.ForeignKey(
                "core.account.id",
                ondelete="RESTRICT",
                name="idempotency_key_account_id_fkey",
            ),
            nullable=False,
        ),
        sa.Column("tool", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(tool) BETWEEN 1 AND 200", name="idempotency_key_tool_length"
        ),
        sa.CheckConstraint(
            "char_length(key) BETWEEN 1 AND 200", name="idempotency_key_key_length"
        ),
        sa.UniqueConstraint(
            "account_id", "tool", "key", name="idempotency_key_account_tool_key"
        ),
        schema="mcp",
    )
    op.create_index(
        "idx_idempotency_key_organisation_id",
        "idempotency_key",
        ["organisation_id"],
        schema="mcp",
    )


def downgrade() -> None:
    op.drop_table("idempotency_key", schema="mcp")
    op.execute("DROP SCHEMA mcp")
