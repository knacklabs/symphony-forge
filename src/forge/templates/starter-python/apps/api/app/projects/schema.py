from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class ProjectSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ProjectStatus(StrEnum):
    active = "active"
    archived = "archived"


class ProjectInput(ProjectSchema):
    name: str = Field(min_length=1, max_length=120)
    status: ProjectStatus


class Project(ProjectSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(max_length=120)
    status: ProjectStatus
    created_at_utc: datetime
    updated_at_utc: datetime
    created_by_account_id: UUID
    modified_by_account_id: UUID


class ProjectListQuery(ProjectSchema):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    sort_by: Literal["name", "status", "createdAtUtc", "updatedAtUtc"] = "createdAtUtc"
    sort_order: Literal["asc", "desc"] = "desc"


class ProjectPagination(ProjectSchema):
    page: int
    limit: int
    total_items: int
    total_pages: int


class ProjectListResponse(ProjectSchema):
    items: list[Project]
    pagination: ProjectPagination
