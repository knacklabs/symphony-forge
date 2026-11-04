from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core import Base


class Notification(Base):
    # Waiting entries are an operational log, as in the TypeScript starter.
    __tablename__ = "notification"
    __table_args__ = (
        CheckConstraint(
            "char_length(subject_name) BETWEEN 1 AND 200",
            name="notification_subject_name_length",
        ),
        CheckConstraint(
            "char_length(message) <= 10000", name="notification_message_length"
        ),
        Index("idx_notification_organisation_id_fk", "organisation_id"),
        Index("idx_notification_recipient_account_id_fk", "recipient_account_id"),
        Index("idx_notification_subject_id_fk", "subject_id"),
        Index(
            "idx_notification_list",
            "organisation_id",
            "recipient_account_id",
            text("created_at_utc DESC"),
            text("id DESC"),
            postgresql_where=text("resolved_at_utc IS NULL"),
        ),
        Index(
            "idx_notification_subject_id_open",
            "organisation_id",
            "subject_id",
            postgresql_where=text("resolved_at_utc IS NULL"),
        ),
        {"schema": "notifications"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    organisation_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "core.organisation.id",
            name="notification_organisation_id_fkey",
            ondelete="RESTRICT",
        )
    )
    recipient_account_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "core.account.id",
            name="notification_recipient_account_id_fkey",
            ondelete="RESTRICT",
        )
    )
    subject_id: Mapped[UUID] = mapped_column()
    subject_name: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
