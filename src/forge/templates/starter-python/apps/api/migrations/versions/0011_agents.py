"""Agent accounts with one key each, and the features whose delete and restore tools agents may use."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_agents"
down_revision: str | None = "0010_history_subjects"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "membership",
        sa.Column(
            "is_agent", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        schema="core",
    )
    op.add_column("membership", sa.Column("agent_key_hash", sa.Text()), schema="core")
    op.create_unique_constraint(
        "membership_agent_key_hash_key", "membership", ["agent_key_hash"], schema="core"
    )
    op.add_column(
        "organisation",
        sa.Column(
            "agent_delete_restore",
            sa.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_column("organisation", "agent_delete_restore", schema="core")
    op.drop_constraint(
        "membership_agent_key_hash_key", "membership", schema="core", type_="unique"
    )
    op.drop_column("membership", "agent_key_hash", schema="core")
    op.drop_column("membership", "is_agent", schema="core")
