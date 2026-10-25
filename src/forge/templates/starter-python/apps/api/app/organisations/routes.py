from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
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
    ChangeRoleInput,
    Member,
    MemberListQuery,
    MemberListResponse,
)
from app.organisations.service import OrganisationsService

router = APIRouter(prefix="/api/v1/members", tags=["Organisations"])
MEMBER_CSV_COLUMNS: tuple[CsvColumn[Member], ...] = (
    ("Email", lambda member: member.email),
    ("Role", lambda member: member.role),
    ("Joined (UTC)", lambda member: utc_date_time(member.created_at_utc)),
)


@router.patch(
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


@router.get(
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


@router.get(
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
