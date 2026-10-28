from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import AccountPrincipal
from app.history.models import ChangeRecord
from app.history.schema import HistoryEntry


class Subject(NamedTuple):
    """The changed item; its name prefixes the summary on the Change history screen."""

    id: UUID
    name: str


class HistoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        account: AccountPrincipal,
        action: str,
        summary: str,
        subject: Subject | None = None,
    ) -> None:
        """Adds the row to the caller's session; the caller's one commit saves it with the change."""
        self.db.add(
            ChangeRecord(
                organisation_id=account.organisation_id,
                actor_account_id=account.id,
                actor_email=account.email,
                action=action,
                summary=summary,
                subject_id=subject.id if subject else None,
                subject_name=subject.name if subject else None,
            )
        )

    def list_for_subject(
        self, account: AccountPrincipal, subject_id: UUID, limit: int
    ) -> list[HistoryEntry]:
        """The newest changes to one item in the caller's organisation, newest first."""
        records = self.db.scalars(
            select(ChangeRecord)
            .where(
                ChangeRecord.organisation_id == account.organisation_id,
                ChangeRecord.subject_id == subject_id,
            )
            .order_by(ChangeRecord.created_at_utc.desc(), ChangeRecord.id.desc())
            .limit(limit)
        ).all()
        return [HistoryEntry.model_validate(record) for record in records]

    def list(
        self, account: AccountPrincipal, limit: int | None = 100
    ) -> list[HistoryEntry]:
        statement = (
            select(ChangeRecord)
            .where(ChangeRecord.organisation_id == account.organisation_id)
            .order_by(ChangeRecord.created_at_utc.desc(), ChangeRecord.id.desc())
        )
        if limit is not None:
            statement = statement.limit(limit)
        # The organisation-wide list names the changed item, as in "Migration plan: Created the project".
        return [
            HistoryEntry.model_validate(record).model_copy(
                update={"summary": f"{record.subject_name}: {record.summary}"}
            )
            if record.subject_name
            else HistoryEntry.model_validate(record)
            for record in self.db.scalars(statement).all()
        ]
