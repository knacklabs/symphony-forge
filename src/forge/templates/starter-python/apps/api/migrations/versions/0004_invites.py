"""Single-use email invites for organisation members."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_invites"
down_revision: str | None = "0003_organisations"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invite",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "organisation_id",
            sa.Uuid(),
            sa.ForeignKey("organisation.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_by_account_id",
            sa.Uuid(),
            sa.ForeignKey("account.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "modified_by_account_id",
            sa.Uuid(),
            sa.ForeignKey("account.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint("organisation_id", "email"),
    )
    for field in ("organisation_id", "created_by_account_id", "modified_by_account_id"):
        op.create_index(f"idx_invite_{field}", "invite", [field])


def downgrade() -> None:
    op.drop_table("invite")
