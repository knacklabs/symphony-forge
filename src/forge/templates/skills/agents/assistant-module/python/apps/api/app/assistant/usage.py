from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.assistant.model import ModelSettings
from app.core import AccountPrincipal, Base

LIMIT_MESSAGE = (
    "The assistant has reached this month's spend limit. Please try again next month."
)


class Usage(Base):
    # Append-only cost log, independent of private chat retention.
    __tablename__ = "usage"
    __table_args__ = (
        CheckConstraint("cost_micros >= 0", name="usage_cost_micros_nonnegative"),
        Index("idx_usage_created_at_utc", "created_at_utc"),
        Index("idx_usage_organisation_id_fk", "organisation_id"),
        Index("idx_usage_account_id_fk", "account_id"),
        {"schema": "assistant"},
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    organisation_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "core.organisation.id",
            name="usage_organisation_id_fkey",
            ondelete="RESTRICT",
        )
    )
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.account.id", name="usage_account_id_fkey", ondelete="RESTRICT")
    )
    cost_micros: Mapped[int] = mapped_column(BigInteger)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UsageService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def month_cost_micros(self, now: datetime) -> int:
        start = now.astimezone(UTC).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        end = (
            start.replace(year=start.year + 1, month=1)
            if start.month == 12
            else start.replace(month=start.month + 1)
        )
        # The owner chose an app-wide cap, including every organisation.
        return int(
            self.session.scalar(
                select(func.coalesce(func.sum(Usage.cost_micros), 0)).where(
                    Usage.created_at_utc >= start, Usage.created_at_utc < end
                )
            )
            or 0
        )

    def can_start(self, settings: ModelSettings, now: datetime) -> bool:
        return self.month_cost_micros(now) < settings.cap_micros

    def record(
        self, principal: AccountPrincipal, cost_micros: int, now: datetime | None = None
    ) -> Usage:
        usage = Usage(
            organisation_id=principal.organisation_id,
            account_id=principal.id,
            cost_micros=cost_micros,
            created_at_utc=now or datetime.now(UTC),
        )
        self.session.add(usage)
        self.session.commit()
        return usage
