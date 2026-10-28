from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
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

from app.core import Base, Role


class Invite(Base):
    # Invites are temporary credentials, so claiming one removes it instead of soft deleting it.
    __tablename__ = "invite"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="invite_email_lower"),
        UniqueConstraint("organisation_id", "email"),
        Index("idx_invite_organisation_id", "organisation_id"),
        Index("idx_invite_created_by_account_id", "created_by_account_id"),
        Index("idx_invite_modified_by_account_id", "modified_by_account_id"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    organisation_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organisation.id", ondelete="RESTRICT")
    )
    email: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT")
    )
    modified_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT")
    )


class Organisation(Base):
    __tablename__ = "organisation"
    __table_args__ = (
        Index("idx_organisation_created_by_account_id", "created_by_account_id"),
        Index("idx_organisation_modified_by_account_id", "modified_by_account_id"),
        Index("idx_organisation_deleted_by_account_id", "deleted_by_account_id"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT")
    )
    modified_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT")
    )
    deleted_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT")
    )
    # The features whose delete and restore tools agents may use.
    agent_delete_restore: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'")
    )


class Membership(Base):
    __tablename__ = "membership"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="membership_role_allowed"),
        Index("idx_membership_created_by_account_id", "created_by_account_id"),
        Index("idx_membership_modified_by_account_id", "modified_by_account_id"),
        Index("idx_membership_deleted_by_account_id", "deleted_by_account_id"),
        Index("idx_membership_organisation_id", "organisation_id"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    organisation_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organisation.id", ondelete="RESTRICT")
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT"), unique=True
    )
    email: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(Text)
    is_agent: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # The SHA-256 of the agent's one key; None when it has none.
    agent_key_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT")
    )
    modified_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT")
    )
    deleted_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT")
    )

    @property
    def has_key(self) -> bool:
        return self.agent_key_hash is not None
