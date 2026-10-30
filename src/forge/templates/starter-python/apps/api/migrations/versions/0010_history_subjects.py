"""Name the changed item on each change, so a detail screen lists its own changes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_history_subjects"
down_revision: str | None = "0009_columns"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("change_record", sa.Column("subject_id", sa.Uuid()), schema="history")
    op.add_column(
        "change_record", sa.Column("subject_name", sa.Text()), schema="history"
    )
    op.create_check_constraint(
        "change_record_subject_name_length",
        "change_record",
        "char_length(subject_name) <= 200",
        schema="history",
    )
    op.create_index(
        "idx_change_record_organisation_id_subject_id_created_at_utc",
        "change_record",
        ["organisation_id", "subject_id", sa.text("created_at_utc DESC")],
        schema="history",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_change_record_organisation_id_subject_id_created_at_utc",
        "change_record",
        schema="history",
    )
    op.drop_constraint(
        "change_record_subject_name_length",
        "change_record",
        schema="history",
        type_="check",
    )
    op.drop_column("change_record", "subject_name", schema="history")
    op.drop_column("change_record", "subject_id", schema="history")
