"""Store private chat ownership; LangGraph setup owns its checkpoint tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_assistant"
down_revision: str | None = "20261105_notifications"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS assistant")
    op.create_table(
        "chat",
        sa.Column(
            "id", sa.Uuid(), primary_key=True, server_default=sa.text("uuidv7()")
        ),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("modified_by_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "last_message_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["organisation_id"],
            ["core.organisation.id"],
            name="chat_organisation_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_account_id"],
            ["core.account.id"],
            name="chat_created_by_account_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["modified_by_account_id"],
            ["core.account.id"],
            name="chat_modified_by_account_id_fkey",
            ondelete="RESTRICT",
        ),
        schema="assistant",
    )
    op.create_index(
        "idx_chat_list",
        "chat",
        [
            "organisation_id",
            "created_by_account_id",
            sa.text("last_message_at_utc DESC"),
            sa.text("id DESC"),
        ],
        schema="assistant",
    )
    for column in ("created_by_account_id", "modified_by_account_id"):
        op.create_index(f"idx_chat_{column}_fk", "chat", [column], schema="assistant")
    op.create_index(
        "idx_chat_last_message_at_utc",
        "chat",
        ["last_message_at_utc"],
        schema="assistant",
    )
    op.execute(
        "CREATE TRIGGER chat_set_updated_at BEFORE UPDATE ON assistant.chat "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.drop_table("chat", schema="assistant")
    # Checkpointer tables are retained: a downgrade must not erase private data
    # outside the retention path. A later upgrade can reuse the schema.
