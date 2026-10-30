from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

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
from app.history.schema import HistoryEntry
from app.history.service import HistoryService

router = APIRouter(prefix="/api/v1/history", tags=["History"])
HISTORY_CSV_COLUMNS: tuple[CsvColumn[HistoryEntry], ...] = (
    ("When (UTC)", lambda record: utc_date_time(record.created_at_utc)),
    ("Who", lambda record: record.actor_email),
    ("What", lambda record: record.summary),
)


@router.get(
    "",
    response_model=SuccessEnvelope[list[HistoryEntry]],
    responses={status: {"model": ErrorEnvelope} for status in (401, 403)},
    summary="List your organisation’s newest 100 changes.",
    description="Only admins can read change history. Changes are returned newest first.",
)
def list_history(
    account: Annotated[AccountPrincipal, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[list[HistoryEntry]]:
    return SuccessEnvelope(data=HistoryService(db).list(account))


@router.get(
    "/export",
    response_class=Response,
    responses={
        200: {"description": "The history.csv file: When (UTC), Who and What."},
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
    },
    summary="Download every change in your organisation.",
    description="Only admins can export change history. The file includes all changes, newest first.",
)
def export_history(
    account: Annotated[AccountPrincipal, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    return csv_response(
        "history.csv", HISTORY_CSV_COLUMNS, HistoryService(db).list(account, None)
    )
