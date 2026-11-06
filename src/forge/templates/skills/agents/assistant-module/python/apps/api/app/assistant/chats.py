from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.assistant.models import Chat
from app.core import AccountPrincipal, ApiError


class ChatService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, principal: AccountPrincipal, now: datetime | None = None) -> Chat:
        chat = Chat(
            organisation_id=principal.organisation_id,
            created_by_account_id=principal.id,
            modified_by_account_id=principal.id,
            last_message_at_utc=now if now is not None else datetime.now(UTC),
        )
        self.session.add(chat)
        self.session.commit()
        return chat

    def own_chat(self, principal: AccountPrincipal, chat_id: UUID) -> Chat:
        chat = self.session.scalar(
            select(Chat).where(
                Chat.id == chat_id,
                Chat.organisation_id == principal.organisation_id,
                Chat.created_by_account_id == principal.id,
            )
        )
        if chat is None:
            raise ApiError(
                404, "NOT_FOUND", "This chat is not available. Start a new chat."
            )
        return chat

    def touch(
        self, principal: AccountPrincipal, chat_id: UUID, now: datetime | None = None
    ) -> None:
        changed = self.session.scalar(
            update(Chat)
            .where(
                Chat.id == chat_id,
                Chat.organisation_id == principal.organisation_id,
                Chat.created_by_account_id == principal.id,
            )
            .values(
                last_message_at_utc=now if now is not None else datetime.now(UTC),
                modified_by_account_id=principal.id,
            )
            .returning(Chat.id)
        )
        if changed is None:
            raise ApiError(
                404, "NOT_FOUND", "This chat is not available. Start a new chat."
            )
        self.session.commit()
