from fastapi import APIRouter

from app.auth.routes import agents_router, current_account, invites_router, require_csrf
from app.auth.routes import router as auth_router
from app.auth.schema import CredentialsInput
from app.auth.service import AuthService, account_emails

router = APIRouter()
router.include_router(auth_router)
router.include_router(invites_router)
router.include_router(agents_router)

__all__ = [
    "AuthService",
    "CredentialsInput",
    "account_emails",
    "current_account",
    "require_csrf",
    "router",
]
