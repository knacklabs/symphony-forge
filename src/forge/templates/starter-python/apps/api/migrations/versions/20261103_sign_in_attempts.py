"""Count failed sign-ins for known and unknown emails alike."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261103_sign_in_attempts"
down_revision: str | None = "0013_via_agent"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sign_in_attempt",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("uuidv7()"), primary_key=True
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("email", name="sign_in_attempt_email_key"),
        sa.CheckConstraint("email = lower(email)", name="sign_in_attempt_email_lower"),
        sa.CheckConstraint(
            "char_length(email) BETWEEN 1 AND 254", name="sign_in_attempt_email_length"
        ),
        schema="core",
    )
    op.execute(
        "CREATE TRIGGER sign_in_attempt_set_updated_at BEFORE UPDATE ON core.sign_in_attempt FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("sign_in_attempt", schema="core")
