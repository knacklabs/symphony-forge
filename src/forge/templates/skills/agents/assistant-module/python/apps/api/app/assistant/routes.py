from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Path, Query, Request
from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy.orm import Session

from app.assistant.chats import ChatService
from app.assistant.schema import (
    ChatId,
    ChatListQuery,
    ChatListResponse,
    ChatResponse,
    CreateChat,
)
from app.auth import current_account, require_csrf
from app.core import (
    AccountPrincipal,
    ErrorEnvelope,
    SuccessEnvelope,
    create_once,
    get_db,
)

router = APIRouter(prefix="/api/v1/assistant/chats", tags=["Assistant"])


@router.post(
    "",
    status_code=201,
    response_model=SuccessEnvelope[ChatId],
    summary="Start a private chat.",
    description="Only the signed-in person can read this chat. Reuse the retry key after a failed request.",
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
    },
)
def create_chat(
    input_data: CreateChat,
    account: Annotated[AccountPrincipal, Depends(current_account)],
    _csrf: Annotated[None, Depends(require_csrf)],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
) -> SuccessEnvelope[ChatId]:
    if idempotency_key is not None:
        chat_id = create_once(
            db,
            account,
            "assistant_chats_create",
            idempotency_key,
            lambda after_create: (
                ChatService(db).create(account, after_create=after_create).id
            ),
        )
        chat = ChatService(db).own_chat(account, chat_id)
    else:
        chat = ChatService(db).create(account)
    return SuccessEnvelope(data=ChatId(id=chat.id))


@router.get(
    "",
    response_model=SuccessEnvelope[ChatListResponse],
    summary="List your private chats.",
    description="Chats appear newest first. Other people's chats never appear.",
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
def list_chats(
    account: Annotated[AccountPrincipal, Depends(current_account)],
    query: Annotated[ChatListQuery, Query()],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[ChatListResponse]:
    return SuccessEnvelope(data=ChatService(db).list(account, query))


@router.get(
    "/{chat_id}",
    response_model=SuccessEnvelope[ChatResponse],
    summary="Read your private chat.",
    description="Returns messages and the pending confirm card. Another person's chat returns 404, including for an admin.",
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
    },
)
def get_chat(
    request: Request,
    chat_id: Annotated[
        UUID,
        Path(
            description="The private chat identifier.",
            examples=["b3e1d349-1d8e-481c-8c69-99ea576f94c7"],
        ),
    ],
    account: Annotated[AccountPrincipal, Depends(current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[ChatResponse]:
    return SuccessEnvelope(
        data=ChatService(db).get(
            account,
            chat_id,
            cast(PostgresSaver, request.app.state.assistant_checkpoints),
        )
    )
