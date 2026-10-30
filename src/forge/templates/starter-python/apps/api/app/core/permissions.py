"""Which role may do what: each module fills this map once, at import."""

from collections.abc import Callable
from typing import Annotated, NamedTuple

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ApiError
from app.core.principal import AccountPrincipal, Role


class FeaturePermissions(NamedTuple):
    view: str
    create: str
    edit: str
    delete: str
    restore: str


_ROLE_PERMISSIONS: dict[Role, list[str]] = {"admin": [], "member": []}


def define_permissions(
    feature: str, roles: dict[Role, list[str]]
) -> FeaturePermissions:
    for role, actions in roles.items():
        _ROLE_PERMISSIONS[role].extend(f"{feature}.{action}" for action in actions)
    return FeaturePermissions(
        *(f"{feature}.{action}" for action in FeaturePermissions._fields)
    )


def permissions_for(role: Role) -> list[str]:
    return list(_ROLE_PERMISSIONS[role])


def has_permission(role: Role, permission: str) -> bool:
    return permission in _ROLE_PERMISSIONS[role]


def require_permission(
    permission: str,
) -> Callable[[Request, Session], AccountPrincipal]:
    def dependency(
        request: Request, db: Annotated[Session, Depends(get_db)]
    ) -> AccountPrincipal:
        # Resolve auth at request time, as admin_only does, to avoid its import cycle.
        from app.auth import current_account

        account = current_account(request, db)
        if not has_permission(account.role, permission):
            raise ApiError(
                403, "PERMISSION_DENIED", "You do not have permission to do this."
            )
        return account

    return dependency
