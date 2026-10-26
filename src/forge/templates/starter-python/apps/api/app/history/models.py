from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core import Base


class ChangeRecord(Base):
    # History is a log: keep the actor's email as it was when the action happened.
    __tablename__ = "change_record"
    __table_args__ = (
        Index(
            "idx_change_record_organisation_id_created_at_utc",
            "organisation_id",
            "created_at_utc",
        ),
        Index("idx_change_record_actor_account_id", "actor_account_id"),
        Index(
            "idx_change_record_organisation_id_subject_id_created_at_utc",
            "organisation_id",
            "subject_id",
            text("created_at_utc DESC"),
        ),
        CheckConstraint(
            "char_length(subject_name) <= 200", name="change_record_subject_name_length"
        ),
        {"schema": "history"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    organisation_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organisation.id", ondelete="RESTRICT")
    )
    actor_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT")
    )
    actor_email: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    # The changed item, such as a project, so its detail screen can list its own changes.
    subject_id: Mapped[UUID | None] = mapped_column()
    subject_name: Mapped[str | None] = mapped_column(Text)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
