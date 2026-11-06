import base64
import binascii
import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.assistant.models import Chat
from app.assistant.schema import (
    ChatListQuery,
    ChatListResponse,
    ChatResponse,
    ChatSummary,
    ConfirmProps,
    Message,
    Paging,
)
from app.core import AccountPrincipal, ApiError

TOTAL_CAP = 10_000


def _cursor(chat: Chat) -> str:
    value = json.dumps(
        [chat.last_message_at_utc.isoformat(), str(chat.id)], separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _cursor_values(value: str, field: str) -> tuple[datetime, UUID]:
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        parsed: object = json.loads(decoded)
        if not isinstance(parsed, list) or len(parsed) != 2:
            raise ValueError
        raw_timestamp, raw_chat_id = parsed
        if not isinstance(raw_timestamp, str) or not isinstance(raw_chat_id, str):
            raise ValueError
        timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError
        chat_id = UUID(raw_chat_id)
    except (binascii.Error, ValueError):
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "The chat cursor is not valid. Load the list again.",
            {
                "fieldErrors": [
                    {
                        "field": field,
                        "reason": "Load the list again to get a valid cursor.",
                    }
                ]
            },
        ) from None
    return timestamp.astimezone(UTC), chat_id


class ChatService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        principal: AccountPrincipal,
        now: datetime | None = None,
        after_create: Callable[[Session, UUID], None] | None = None,
    ) -> Chat:
        chat = Chat(
            organisation_id=principal.organisation_id,
            created_by_account_id=principal.id,
            modified_by_account_id=principal.id,
            last_message_at_utc=now if now is not None else datetime.now(UTC),
        )
        self.session.add(chat)
        self.session.flush()
        if after_create is not None:
            after_create(self.session, chat.id)
        self.session.commit()
        return chat

    def list(
        self, principal: AccountPrincipal, query: ChatListQuery
    ) -> ChatListResponse:
        owner = (
            Chat.organisation_id == principal.organisation_id,
            Chat.created_by_account_id == principal.id,
        )
        cursor = query.before if query.before is not None else query.after
        backward = query.before is not None
        statement = select(Chat).where(*owner)
        if cursor is not None:
            timestamp, chat_id = _cursor_values(
                cursor, "before" if backward else "after"
            )
            boundary = (
                or_(
                    Chat.last_message_at_utc > timestamp,
                    and_(Chat.last_message_at_utc == timestamp, Chat.id > chat_id),
                )
                if backward
                else or_(
                    Chat.last_message_at_utc < timestamp,
                    and_(Chat.last_message_at_utc == timestamp, Chat.id < chat_id),
                )
            )
            statement = statement.where(boundary)

        direction = (
            Chat.last_message_at_utc.asc()
            if backward
            else Chat.last_message_at_utc.desc()
        )
        id_direction = Chat.id.asc() if backward else Chat.id.desc()
        rows = list(
            self.session.scalars(
                statement.order_by(direction, id_direction).limit(query.limit + 1)
            )
        )
        more = len(rows) > query.limit
        items = rows[: query.limit]
        if backward:
            items.reverse()

        total = self.session.scalar(
            select(func.count()).select_from(
                select(Chat.id).where(*owner).limit(TOTAL_CAP + 1).subquery()
            )
        )
        first = items[0] if items else None
        last = items[-1] if items else None
        return ChatListResponse(
            items=[ChatSummary.model_validate(chat) for chat in items],
            paging=Paging(
                limit=query.limit,
                next_cursor=(
                    _cursor(last) if last is not None and (backward or more) else None
                ),
                previous_cursor=(
                    _cursor(first)
                    if first is not None and (more if backward else cursor is not None)
                    else None
                ),
                total=min(total or 0, TOTAL_CAP),
                total_capped=(total or 0) > TOTAL_CAP,
            ),
        )

    def get(
        self, principal: AccountPrincipal, chat_id: UUID, saver: PostgresSaver
    ) -> ChatResponse:
        chat = self.own_chat(principal, chat_id)
        saved = saver.get_tuple({"configurable": {"thread_id": str(chat.id)}})
        messages: list[Message] = []
        if saved is not None:
            channel_values = saved.checkpoint.get("channel_values", {})
            stored = channel_values.get("messages", [])
            if isinstance(stored, list):
                for message in stored:
                    if not isinstance(message, BaseMessage):
                        continue
                    if message.type not in {"human", "ai"}:
                        continue
                    content = message.content
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        text = "".join(
                            part["text"]
                            for part in content
                            if isinstance(part, dict)
                            and part.get("type") == "text"
                            and isinstance(part.get("text"), str)
                        )
                    else:
                        text = ""
                    messages.append(
                        Message(
                            role="user" if message.type == "human" else "assistant",
                            text=text,
                        )
                    )

        confirm = None
        pending_writes = saved.pending_writes if saved is not None else None
        for _, channel, value in pending_writes or ():
            if channel != "__interrupt__" or not isinstance(value, (list, tuple)):
                continue
            for interrupt in value:
                if not isinstance(interrupt.value, dict):
                    continue
                confirm = ConfirmProps.model_validate(
                    {
                        **interrupt.value,
                        "confirmId": interrupt.id,
                    }
                )

        return ChatResponse(
            id=chat.id,
            created_at_utc=chat.created_at_utc,
            last_message_at_utc=chat.last_message_at_utc,
            messages=messages,
            confirm=confirm,
        )

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
