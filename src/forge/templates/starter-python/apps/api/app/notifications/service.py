from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import AccountPrincipal
from app.notifications.models import Notification
from app.notifications.schema import NotificationEntry, NotificationsList


class NotificationsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def notify(
        self,
        account: AccountPrincipal,
        recipient_account_id: UUID,
        subject_id: UUID,
        subject_name: str,
        message: str,
        tx: Session | None = None,
    ) -> None:
        """Add to the caller's transaction; its commit saves the entry with the change."""
        db = tx if tx is not None else self.db
        db.add(
            Notification(
                organisation_id=account.organisation_id,
                recipient_account_id=recipient_account_id,
                subject_id=subject_id,
                subject_name=subject_name,
                message=message,
            )
        )
        db.flush()

    def resolve(
        self, account: AccountPrincipal, subject_id: UUID, tx: Session | None = None
    ) -> None:
        """Close every open entry for this record in the same organisation and save."""
        db = tx if tx is not None else self.db
        db.execute(
            update(Notification)
            .where(
                Notification.organisation_id == account.organisation_id,
                Notification.subject_id == subject_id,
                Notification.resolved_at_utc.is_(None),
            )
            .values(resolved_at_utc=func.now())
        )

    def list(self, account: AccountPrincipal) -> NotificationsList:
        scope = (
            Notification.organisation_id == account.organisation_id,
            Notification.recipient_account_id == account.id,
            Notification.resolved_at_utc.is_(None),
        )
        count = self.db.scalar(
            select(func.count()).select_from(Notification).where(*scope)
        )
        records = self.db.scalars(
            select(Notification)
            .where(*scope)
            .order_by(Notification.created_at_utc.desc(), Notification.id.desc())
            .limit(100)
        ).all()
        return NotificationsList(
            count=count or 0,
            items=[NotificationEntry.model_validate(row) for row in records],
        )
