"""Scope projects to organisations and give each account one membership."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_organisations"
down_revision: str | None = "0002_soft_delete_only"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

membership_role = postgresql.ENUM(
    "admin", "member", name="membership_role", create_type=False
)


def upgrade() -> None:
    membership_role.create(op.get_bind(), checkfirst=True)
    for table in ("organisation", "membership"):
        columns = [
            sa.Column("id", sa.Uuid(), primary_key=True),
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
            sa.Column("deleted_at_utc", sa.DateTime(timezone=True)),
            sa.Column(
                "deleted_by_account_id",
                sa.Uuid(),
                sa.ForeignKey("account.id", ondelete="RESTRICT"),
            ),
        ]
        if table == "membership":
            columns.extend(
                [
                    sa.Column(
                        "organisation_id",
                        sa.Uuid(),
                        sa.ForeignKey("organisation.id", ondelete="RESTRICT"),
                        nullable=False,
                    ),
                    sa.Column(
                        "account_id",
                        sa.Uuid(),
                        sa.ForeignKey("account.id", ondelete="RESTRICT"),
                        nullable=False,
                        unique=True,
                    ),
                    sa.Column("email", sa.String(254), nullable=False),
                    sa.Column("role", membership_role, nullable=False),
                ]
            )
        op.create_table(table, *columns)
        for field in (
            "created_by_account_id",
            "modified_by_account_id",
            "deleted_by_account_id",
        ):
            op.create_index(f"idx_{table}_{field}", table, [field])
    op.create_index("idx_membership_organisation_id", "membership", ["organisation_id"])
    # A starter database is empty: there are no projects to backfill.
    op.add_column("project", sa.Column("organisation_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "project_organisation_id_fkey",
        "project",
        "organisation",
        ["organisation_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("idx_project_organisation_id", "project", ["organisation_id"])
    op.drop_index("idx_project_account_id", table_name="project")
    op.drop_constraint("project_account_id_fkey", "project", type_="foreignkey")
    op.drop_column("project", "account_id")


def downgrade() -> None:
    op.add_column("project", sa.Column("account_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "project_account_id_fkey",
        "project",
        "account",
        ["account_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("idx_project_account_id", "project", ["account_id"])
    op.drop_index("idx_project_organisation_id", table_name="project")
    op.drop_constraint("project_organisation_id_fkey", "project", type_="foreignkey")
    op.drop_column("project", "organisation_id")
    op.drop_table("membership")
    op.drop_table("organisation")
    membership_role.drop(op.get_bind(), checkfirst=True)
