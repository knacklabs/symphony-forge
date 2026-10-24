from fastapi import APIRouter

from app.auth.routes import current_account, invites_router, require_csrf
from app.auth.routes import router as auth_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(invites_router)

__all__ = ["current_account", "require_csrf", "router"]
