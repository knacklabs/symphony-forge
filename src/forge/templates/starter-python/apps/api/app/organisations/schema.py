from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core import Role


class OrganisationSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        from_attributes=True,
    )


class Member(OrganisationSchema):
    id: UUID
    account_id: UUID
    email: str = Field(max_length=254, examples=["ada@example.com"])
    role: Role
    created_at_utc: datetime


class MemberListQuery(OrganisationSchema):
    page: int = Field(
        default=1, ge=1, description="The one-based page number.", examples=[1]
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Members per page, up to 100.",
        examples=[20],
    )


class MemberPagination(OrganisationSchema):
    page: int
    limit: int
    total_items: int
    total_pages: int


class MemberListResponse(OrganisationSchema):
    items: list[Member]
    pagination: MemberPagination
