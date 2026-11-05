from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import current_account
from app.core import AccountPrincipal, ErrorEnvelope, SuccessEnvelope, get_db
from app.notifications.schema import NotificationsList
from app.notifications.service import NotificationsService

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=SuccessEnvelope[NotificationsList],
    responses={401: {"model": ErrorEnvelope}},
    summary="List the records that wait for you, with a count.",
    description="Only your open entries in your organisation, newest first. Returns up to 100 entries and the count of all open entries.",
)
def list_notifications(
    account: Annotated[AccountPrincipal, Depends(current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> SuccessEnvelope[NotificationsList]:
    return SuccessEnvelope(data=NotificationsService(db).list(account))
