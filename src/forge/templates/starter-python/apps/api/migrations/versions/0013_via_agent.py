"""Record the agent acting for a person in change history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_via_agent"
down_revision: str | None = "0012_mcp"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "change_record",
        sa.Column("via_agent", sa.Text(), nullable=True),
        schema="history",
    )


def downgrade() -> None:
    op.drop_column("change_record", "via_agent", schema="history")
