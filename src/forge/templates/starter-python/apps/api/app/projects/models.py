from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core import Base
from app.projects.schema import ProjectStatus


class Project(Base):
    __tablename__ = "project"
    __table_args__ = (
        Index("idx_project_account_id", "account_id"),
        Index("idx_project_created_by_account_id", "created_by_account_id"),
        Index("idx_project_modified_by_account_id", "modified_by_account_id"),
        Index("idx_project_deleted_by_account_id", "deleted_by_account_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", native_enum=True),
        nullable=False,
        default=ProjectStatus.active,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT"), nullable=False
    )
    modified_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT"), nullable=False
    )
    deleted_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT")
    )
