from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ApiError
from app.core.principal import AccountPrincipal
from app.core.security import verify_csrf


def admin_only(
    request: Request, db: Annotated[Session, Depends(get_db)]
) -> AccountPrincipal:
    # Resolve auth at request time, as the organisations router does, to avoid its import cycle.
    from app.auth import current_account

    account = current_account(request, db)
    if account.role != "admin":
        raise ApiError(403, "ADMIN_ONLY", "Only an admin can do this.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        verify_csrf(request)
    return account
