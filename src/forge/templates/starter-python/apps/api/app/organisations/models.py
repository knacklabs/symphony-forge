from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core import Base, Role


class Organisation(Base):
    __tablename__ = "organisation"
    __table_args__ = (
        Index("idx_organisation_created_by_account_id", "created_by_account_id"),
        Index("idx_organisation_modified_by_account_id", "modified_by_account_id"),
        Index("idx_organisation_deleted_by_account_id", "deleted_by_account_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT")
    )
    modified_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT")
    )
    deleted_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT")
    )


class Membership(Base):
    __tablename__ = "membership"
    __table_args__ = (
        Index("idx_membership_created_by_account_id", "created_by_account_id"),
        Index("idx_membership_modified_by_account_id", "modified_by_account_id"),
        Index("idx_membership_deleted_by_account_id", "deleted_by_account_id"),
        Index("idx_membership_organisation_id", "organisation_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID] = mapped_column(
        ForeignKey("organisation.id", ondelete="RESTRICT")
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT"), unique=True
    )
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[Role] = mapped_column(Enum("admin", "member", name="membership_role"))
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT")
    )
    modified_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT")
    )
    deleted_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT")
    )
