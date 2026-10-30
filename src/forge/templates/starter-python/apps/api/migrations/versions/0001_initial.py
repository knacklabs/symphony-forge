"""Create account, session, password reset token and project tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


project_status = postgresql.ENUM(
    "active", "archived", name="project_status", create_type=False
)


def upgrade() -> None:
    project_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
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
        sa.Column("created_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("modified_by_account_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_account_id"], ["account.id"], ondelete="NO ACTION"
        ),
        sa.ForeignKeyConstraint(
            ["modified_by_account_id"], ["account.id"], ondelete="NO ACTION"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(
        "idx_account_created_by_account_id", "account", ["created_by_account_id"]
    )
    op.create_index(
        "idx_account_modified_by_account_id", "account", ["modified_by_account_id"]
    )

    op.create_table(
        "session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("idx_session_account_id", "session", ["account_id"])
    op.create_index("idx_session_expires_at_utc", "session", ["expires_at_utc"])

    op.create_table(
        "password_reset_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "idx_password_reset_token_account_id", "password_reset_token", ["account_id"]
    )
    op.create_index(
        "idx_password_reset_token_expires_at_utc",
        "password_reset_token",
        ["expires_at_utc"],
    )

    op.create_table(
        "project",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", project_status, nullable=False),
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
        sa.Column("created_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("modified_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("deleted_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_account_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["created_by_account_id"], ["account.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["modified_by_account_id"], ["account.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by_account_id"], ["account.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_project_account_id", "project", ["account_id"])
    op.create_index(
        "idx_project_created_by_account_id", "project", ["created_by_account_id"]
    )
    op.create_index(
        "idx_project_modified_by_account_id", "project", ["modified_by_account_id"]
    )
    op.create_index(
        "idx_project_deleted_by_account_id", "project", ["deleted_by_account_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_project_deleted_by_account_id", table_name="project")
    op.drop_index("idx_project_modified_by_account_id", table_name="project")
    op.drop_index("idx_project_created_by_account_id", table_name="project")
    op.drop_index("idx_project_account_id", table_name="project")
    op.drop_table("project")
    op.drop_index(
        "idx_password_reset_token_expires_at_utc", table_name="password_reset_token"
    )
    op.drop_index(
        "idx_password_reset_token_account_id", table_name="password_reset_token"
    )
    op.drop_table("password_reset_token")
    op.drop_index("idx_session_expires_at_utc", table_name="session")
    op.drop_index("idx_session_account_id", table_name="session")
    op.drop_table("session")
    op.drop_index("idx_account_modified_by_account_id", table_name="account")
    op.drop_index("idx_account_created_by_account_id", table_name="account")
    op.drop_table("account")
    project_status.drop(op.get_bind(), checkfirst=True)
