from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Response
from sqlalchemy.orm import Session

from app.auth import current_account
from app.core import (
    AccountPrincipal,
    CsvColumn,
    ErrorEnvelope,
    SuccessEnvelope,
    admin_only,
    csv_response,
    get_db,
    utc_date_time,
)
from app.history import HistoryService
from app.organisations.schema import (
    AgentKey,
    AgentTools,
    AgentToolsChange,
    ChangeRoleInput,
    Member,
    MemberListQuery,
    MemberListResponse,
)
from app.organisations.service import OrganisationsService

members_router = APIRouter(prefix="/api/v1/members", tags=["Organisations"])
agent_tools_router = APIRouter(prefix="/api/v1/agent-tools", tags=["Organisations"])
MEMBER_CSV_COLUMNS: tuple[CsvColumn[Member], ...] = (
    ("Email", lambda member: member.email),
    ("Role", lambda member: member.role),
    ("Joined (UTC)", lambda member: utc_date_time(member.created_at_utc)),
)


@members_router.patch(
    "/{account_id}",
    response_model=SuccessEnvelope[Member],
    responses={status: {"model": ErrorEnvelope} for status in (400, 401, 403, 404)},
    summary="Change another member’s role.",
    description="Only admins can change another member of their own organisation.",
)
def change_role(
    account_id: UUID,
    input_data: ChangeRoleInput,
    account: Annotated[AccountPrincipal, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[Member]:
    return SuccessEnvelope(
        data=OrganisationsService(db, HistoryService(db)).change_role(
            account, account_id, input_data.role
        )
    )


@members_router.get(
    "",
    response_model=SuccessEnvelope[MemberListResponse],
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
    summary="List your organisation’s members, oldest first.",
)
def list_members(
    account: Annotated[AccountPrincipal, Depends(current_account)],
    query: Annotated[MemberListQuery, Query()],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[MemberListResponse]:
    return SuccessEnvelope(
        data=OrganisationsService(db, HistoryService(db)).list(
            account.organisation_id, query
        )
    )


@members_router.get(
    "/export",
    response_class=Response,
    responses={
        200: {"description": "The members.csv file: Email, Role and Joined (UTC)."},
        401: {"model": ErrorEnvelope},
    },
    summary="Download every member of your organisation, oldest first.",
)
def export_members(
    account: Annotated[AccountPrincipal, Depends(current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    return csv_response(
        "members.csv",
        MEMBER_CSV_COLUMNS,
        OrganisationsService(db, HistoryService(db)).list_all(account.organisation_id),
    )


@members_router.post(
    "/{account_id}/key",
    status_code=201,
    response_model=SuccessEnvelope[AgentKey],
    responses={status: {"model": ErrorEnvelope} for status in (401, 403, 404)},
    summary="Create a key for an agent account.",
    description="Only admins can create keys. The key shows this one time only. A new key replaces the old one, which stops working at once.",
)
def create_agent_key(
    account_id: UUID,
    account: Annotated[AccountPrincipal, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[AgentKey]:
    return SuccessEnvelope(
        data=OrganisationsService(db, HistoryService(db)).create_key(
            account, account_id
        )
    )


@members_router.delete(
    "/{account_id}/key",
    response_model=SuccessEnvelope[None],
    responses={status: {"model": ErrorEnvelope} for status in (401, 403, 404)},
    summary="Revoke an agent account’s key.",
    description="Only admins can revoke keys. Agents that use the key stop working at once.",
)
def revoke_agent_key(
    account_id: UUID,
    account: Annotated[AccountPrincipal, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[None]:
    OrganisationsService(db, HistoryService(db)).revoke_key(account, account_id)
    return SuccessEnvelope(data=None)


@agent_tools_router.get(
    "",
    response_model=SuccessEnvelope[AgentTools],
    responses={status: {"model": ErrorEnvelope} for status in (401, 403)},
    summary="List the features whose delete and restore tools agents can use.",
    description="Only admins can read it. Every feature’s search, get, create and update tools are always on.",
)
def list_agent_tools(
    account: Annotated[AccountPrincipal, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[AgentTools]:
    return SuccessEnvelope(
        data=OrganisationsService(db, HistoryService(db)).agent_tools(
            account.organisation_id
        )
    )


@agent_tools_router.put(
    "/{feature}",
    response_model=SuccessEnvelope[AgentTools],
    responses={status: {"model": ErrorEnvelope} for status in (400, 401, 403)},
    summary="Turn agent delete and restore on or off for one feature.",
    description="Only admins can change it. The agent account’s role still applies.",
)
def change_agent_tools(
    feature: Annotated[
        str,
        Path(
            max_length=100,
            pattern=r"^[a-z][a-z0-9-]*$",
            description="The feature’s plural in kebab case.",
            examples=["projects"],
        ),
    ],
    input_data: AgentToolsChange,
    account: Annotated[AccountPrincipal, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[AgentTools]:
    return SuccessEnvelope(
        data=OrganisationsService(db, HistoryService(db)).set_agent_tools(
            account, feature, input_data.delete_and_restore
        )
    )
