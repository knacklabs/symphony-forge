"""Change history for organisation admin actions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_history"
down_revision: str | None = "0004_invites"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_record",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organisation_id",
            sa.Uuid(),
            sa.ForeignKey("organisation.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_account_id",
            sa.Uuid(),
            sa.ForeignKey("account.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_email", sa.String(254), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("summary", sa.String(400), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_change_record_organisation_id_created_at_utc",
        "change_record",
        ["organisation_id", "created_at_utc"],
    )
    op.create_index(
        "idx_change_record_actor_account_id", "change_record", ["actor_account_id"]
    )


def downgrade() -> None:
    op.drop_table("change_record")
