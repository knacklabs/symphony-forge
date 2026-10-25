from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class HistoryEntry(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )

    id: UUID = Field(description="The change identifier.")
    actor_email: str = Field(
        description="The email of the admin who made the change.",
        examples=["ada@example.com"],
    )
    summary: str = Field(
        description="What changed.", examples=["Invited grace@example.com"]
    )
    created_at_utc: datetime = Field(
        description="When the change happened, in UTC.",
        examples=["2026-10-24T11:30:00Z"],
    )
