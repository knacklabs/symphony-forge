# forge:feature:schema-imports:start
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic.alias_generators import to_camel

# forge:feature:schema-imports:end


class ProjectSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


# forge:feature:status-type:start
class ProjectStatus(StrEnum):
    active = "active"
    archived = "archived"


# forge:feature:status-type:end


class ProjectInput(ProjectSchema):
    # forge:feature:input-fields:start
    name: str = Field(min_length=1, max_length=120)
    status: ProjectStatus
    # forge:feature:input-fields:end


class Project(ProjectSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # forge:feature:response-fields:start
    name: str = Field(max_length=120)
    status: ProjectStatus
    # forge:feature:response-fields:end
    created_at_utc: datetime
    updated_at_utc: datetime
    created_by_account_id: UUID
    modified_by_account_id: UUID
    created_by_email: str
    modified_by_email: str
    deleted_at_utc: datetime | None
    deleted_by_email: str | None


# A cursor holds a whole project name, which can be 120 characters of any script.
CURSOR_PATTERN = r"^[A-Za-z0-9_-]{1,2048}$"


class ProjectExportQuery(ProjectSchema):
    """The list's search and filter, so the export downloads what the list shows."""

    search: str | None = Field(default=None, max_length=200)
    # forge:feature:filter-fields:start
    status: ProjectStatus | None = None
    # forge:feature:filter-fields:end
    deleted: Literal["yes"] | None = Field(
        default=None,
        description="Show deleted projects too; only for a caller with the restore permission.",
        examples=["yes"],
    )


class ProjectListQuery(ProjectExportQuery):
    limit: int = Field(default=20, ge=1, le=100)
    # forge:feature:sort-fields:start
    sort_by: Literal["name", "status", "createdAtUtc", "updatedAtUtc"] = "updatedAtUtc"
    # forge:feature:sort-fields:end
    sort_order: Literal["asc", "desc"] = "desc"
    after: str | None = Field(default=None, pattern=CURSOR_PATTERN)
    before: str | None = Field(default=None, pattern=CURSOR_PATTERN)

    @field_validator("before")
    @classmethod
    def _one_cursor(cls, before: str | None, info: ValidationInfo) -> str | None:
        if before is not None and info.data.get("after") is not None:
            raise ValueError("Use after or before, not both.")
        return before


class ProjectPaging(ProjectSchema):
    limit: int
    next_cursor: str | None
    previous_cursor: str | None
    total: int
    total_capped: bool


class ProjectListResponse(ProjectSchema):
    items: list[Project]
    paging: ProjectPaging
