from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class NotificationEntry(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True
    )

    id: UUID = Field(
        description="The waiting entry identifier.",
        examples=["019a3500-0000-7000-8000-000000000001"],
    )
    subject_id: UUID = Field(
        description="The record that needs an action.",
        examples=["019a3500-0000-7000-8000-000000000002"],
    )
    subject_name: str = Field(
        description="The record name.", examples=["October budget"]
    )
    message: str = Field(
        description="The action that waits for you.", examples=["Approve the budget."]
    )
    created_at_utc: datetime = Field(
        description="When the entry was created, in UTC.",
        examples=["2026-10-31T10:00:00Z"],
    )


class NotificationsList(BaseModel):
    count: int = Field(
        description="The number of all records that wait for you.", examples=[2]
    )
    items: list[NotificationEntry] = Field(
        description="Up to 100 open entries, newest first."
    )
