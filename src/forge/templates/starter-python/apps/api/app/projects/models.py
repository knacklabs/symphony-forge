from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    column,
    func,
    select,
    table,
    text,
)
from sqlalchemy.orm import Mapped, column_property, mapped_column

from app.core import Base
from app.projects.schema import ProjectStatus

# The core account table, read only for the emails of the accounts that created and last
# changed a project, through the project's own foreign keys to core.
_account = table("account", column("id"), column("email"), schema="core")


class Project(Base):
    __tablename__ = "project"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived')", name="project_status_allowed"
        ),
        CheckConstraint(
            "char_length(name) BETWEEN 1 AND 120", name="project_name_length"
        ),
        Index("idx_project_organisation_id", "organisation_id"),
        Index("idx_project_created_by_account_id", "created_by_account_id"),
        Index("idx_project_modified_by_account_id", "modified_by_account_id"),
        Index("idx_project_deleted_by_account_id", "deleted_by_account_id"),
        {"schema": "projects"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    organisation_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.organisation.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Text,
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
        ForeignKey("core.account.id", ondelete="RESTRICT"), nullable=False
    )
    modified_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT"), nullable=False
    )
    deleted_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.account.id", ondelete="RESTRICT")
    )
    created_by_email: Mapped[str] = column_property(
        select(_account.c.email)
        .where(_account.c.id == created_by_account_id)
        .scalar_subquery()
    )
    modified_by_email: Mapped[str] = column_property(
        select(_account.c.email)
        .where(_account.c.id == modified_by_account_id)
        .scalar_subquery()
    )
