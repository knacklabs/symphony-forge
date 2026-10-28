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
    is_agent: bool = Field(description="Whether the member is an agent account.")
    has_key: bool = Field(description="Whether the agent account has a working key.")
    created_at_utc: datetime


class ChangeRoleInput(OrganisationSchema):
    role: Role = Field(description="The member’s new role.", examples=["member"])


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


class AgentKey(OrganisationSchema):
    key: str = Field(
        description="The agent’s key. It shows this one time only.",
        examples=["agent_Vb3Qm9xT2kLr8sYw4Nc6Hd1Fj7Pz0Ae5Gu3Ki9Ob2Wl"],
    )


class AgentToolsChange(OrganisationSchema):
    delete_and_restore: bool = Field(
        description="Whether agents can use the feature’s delete and restore tools.",
        examples=[True],
    )


class AgentTools(OrganisationSchema):
    delete_and_restore: list[str] = Field(
        description="The features whose delete and restore tools agents can use.",
        examples=[["projects"]],
    )
