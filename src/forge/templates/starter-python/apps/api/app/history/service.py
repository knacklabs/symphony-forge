from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import AccountPrincipal
from app.history.models import ChangeRecord
from app.history.schema import HistoryEntry


class HistoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        account: AccountPrincipal,
        action: Literal["member.invited", "member.role_changed"],
        summary: str,
    ) -> None:
        self.db.add(
            ChangeRecord(
                organisation_id=account.organisation_id,
                actor_account_id=account.id,
                actor_email=account.email,
                action=action,
                summary=summary,
            )
        )
        self.db.commit()

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
        return [
            HistoryEntry.model_validate(record)
            for record in self.db.scalars(statement).all()
        ]
