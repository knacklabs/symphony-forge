from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core import Base


class IdempotencyKey(Base):
    # ponytail: keys stay with their items; a retention policy needs its own story.
    __tablename__ = "idempotency_key"
    __table_args__ = (
        CheckConstraint(
            "char_length(tool) BETWEEN 1 AND 200", name="idempotency_key_tool_length"
        ),
        CheckConstraint(
            "char_length(key) BETWEEN 1 AND 200", name="idempotency_key_key_length"
        ),
        UniqueConstraint(
            "account_id", "tool", "key", name="idempotency_key_account_tool_key"
        ),
        Index("idx_idempotency_key_organisation_id", "organisation_id"),
        {"schema": "mcp"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    organisation_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "core.organisation.id",
            ondelete="RESTRICT",
            name="idempotency_key_organisation_id_fkey",
        ),
        nullable=False,
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "core.account.id",
            ondelete="RESTRICT",
            name="idempotency_key_account_id_fkey",
        ),
        nullable=False,
    )
    tool: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    item_id: Mapped[UUID] = mapped_column(nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
