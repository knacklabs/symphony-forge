from typing import Literal, NamedTuple
from uuid import UUID

type Role = Literal["admin", "member"]


class AccountPrincipal(NamedTuple):
    id: UUID
    email: str
    organisation_id: UUID
    role: Role
    via_agent: str | None = None
