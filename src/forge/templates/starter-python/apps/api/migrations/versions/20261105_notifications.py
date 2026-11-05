"""Keep records that wait for a person in their own module."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261105_notifications"
down_revision: str | None = "20261103_sign_in_attempts"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA notifications")
    op.create_table(
        "notification",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("uuidv7()"), primary_key=True
        ),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_account_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("subject_name", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at_utc", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["core.organisation.id"],
            name="notification_organisation_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_account_id"],
            ["core.account.id"],
            name="notification_recipient_account_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "char_length(subject_name) BETWEEN 1 AND 200",
            name="notification_subject_name_length",
        ),
        sa.CheckConstraint(
            "char_length(message) <= 10000", name="notification_message_length"
        ),
        schema="notifications",
    )
    for column in ("organisation_id", "recipient_account_id", "subject_id"):
        op.create_index(
            f"idx_notification_{column}_fk",
            "notification",
            [column],
            schema="notifications",
        )
    op.create_index(
        "idx_notification_list",
        "notification",
        [
            "organisation_id",
            "recipient_account_id",
            sa.text("created_at_utc DESC"),
            sa.text("id DESC"),
        ],
        schema="notifications",
        postgresql_where=sa.text("resolved_at_utc IS NULL"),
    )
    op.create_index(
        "idx_notification_subject_id_open",
        "notification",
        ["organisation_id", "subject_id"],
        schema="notifications",
        postgresql_where=sa.text("resolved_at_utc IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("notification", schema="notifications")
    op.execute("DROP SCHEMA notifications")
