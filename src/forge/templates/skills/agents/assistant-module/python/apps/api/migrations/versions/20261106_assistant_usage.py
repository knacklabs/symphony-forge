"""Record assistant costs independently of expiring chats."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_assistant_usage"
down_revision: str | None = "20261106_assistant"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("uuidv7()")
        ),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("cost_micros", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["core.organisation.id"],
            name="usage_organisation_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["core.account.id"],
            name="usage_account_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("cost_micros >= 0", name="usage_cost_micros_nonnegative"),
        schema="assistant",
    )
    for column in ("organisation_id", "account_id", "created_at_utc"):
        suffix = "_fk" if column.endswith("_id") else ""
        op.create_index(
            f"idx_usage_{column}{suffix}", "usage", [column], schema="assistant"
        )


def downgrade() -> None:
    op.drop_table("usage", schema="assistant")
