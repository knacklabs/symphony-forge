from fastapi import APIRouter

from app.auth.routes import current_account, invites_router, require_csrf
from app.auth.routes import router as auth_router
from app.auth.schema import CredentialsInput
from app.auth.service import AuthService

router = APIRouter()
router.include_router(auth_router)
router.include_router(invites_router)

__all__ = [
    "AuthService",
    "CredentialsInput",
    "current_account",
    "require_csrf",
    "router",
]
