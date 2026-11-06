from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core import Base


class Chat(Base):
    # Temporary private data is erased at expiry rather than soft-deleted.
    __tablename__ = "chat"
    __table_args__ = (
        Index(
            "idx_chat_list",
            "organisation_id",
            "created_by_account_id",
            text("last_message_at_utc DESC"),
            text("id DESC"),
        ),
        Index("idx_chat_created_by_account_id_fk", "created_by_account_id"),
        Index("idx_chat_modified_by_account_id_fk", "modified_by_account_id"),
        Index("idx_chat_last_message_at_utc", "last_message_at_utc"),
        {"schema": "assistant"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    organisation_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "core.organisation.id",
            name="chat_organisation_id_fkey",
            ondelete="RESTRICT",
        )
    )
    created_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "core.account.id",
            name="chat_created_by_account_id_fkey",
            ondelete="RESTRICT",
        )
    )
    modified_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "core.account.id",
            name="chat_modified_by_account_id_fkey",
            ondelete="RESTRICT",
        )
    )
    last_message_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
