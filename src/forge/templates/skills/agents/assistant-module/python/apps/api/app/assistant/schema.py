from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic.alias_generators import to_camel


class Schema(BaseModel):
    model_config = ConfigDict(
        extra="forbid", alias_generator=to_camel, populate_by_name=True
    )


class Column(Schema):
    key: str
    label: str


class TableProps(Schema):
    columns: list[Column]
    rows: list[dict[str, str | int | float | None]]
    total: int | None = Field(default=None, ge=0)


class ChartProps(Schema):
    type: Literal["bar", "line"]
    x_key: str
    series: list[Column]
    rows: list[dict[str, str | int | float]]
    unit: str | None = None


class Tile(Schema):
    label: str
    value: str | int | float
    unit: str | None = None


class StatsProps(Schema):
    tiles: list[Tile]


class DetailField(Schema):
    label: str
    value: str | int | float | None


class DetailProps(Schema):
    title: str
    fields: list[DetailField]


class ConfirmProps(Schema):
    confirm_id: str
    title: str
    lines: list[str]
    expires_at: datetime


class TableBlock(Schema):
    kind: Literal["table"] = "table"
    props: TableProps


class ChartBlock(Schema):
    kind: Literal["chart"] = "chart"
    props: ChartProps


class StatsBlock(Schema):
    kind: Literal["stats"] = "stats"
    props: StatsProps


class DetailBlock(Schema):
    kind: Literal["detail"] = "detail"
    props: DetailProps


class ConfirmBlock(Schema):
    kind: Literal["confirm"] = "confirm"
    props: ConfirmProps


Block = Annotated[
    TableBlock | ChartBlock | StatsBlock | DetailBlock | ConfirmBlock,
    Field(discriminator="kind"),
]


class TextDelta(Schema):
    delta: str


class Notice(Schema):
    message: str


class TextEvent(Schema):
    event: Literal["text"] = "text"
    data: TextDelta


class BlockEvent(Schema):
    event: Literal["block"] = "block"
    data: Block


class ConfirmEvent(Schema):
    event: Literal["confirm"] = "confirm"
    data: ConfirmProps


class LimitEvent(Schema):
    event: Literal["limit"] = "limit"
    data: Notice


class ErrorEvent(Schema):
    event: Literal["error"] = "error"
    data: Notice


class DoneEvent(Schema):
    event: Literal["done"] = "done"
    data: Schema


StreamEvent = Annotated[
    TextEvent | BlockEvent | ConfirmEvent | LimitEvent | ErrorEvent | DoneEvent,
    Field(discriminator="event"),
]


class CreateChat(Schema):
    model_config = ConfigDict(str_strip_whitespace=True)


class ChatId(Schema):
    id: UUID


class ChatSummary(ChatId):
    model_config = ConfigDict(from_attributes=True)
    created_at_utc: datetime
    last_message_at_utc: datetime


class Message(Schema):
    role: Literal["user", "assistant"]
    text: str


class ChatResponse(ChatSummary):
    messages: list[Message]
    confirm: ConfirmProps | None


class ChatListQuery(Schema):
    model_config = ConfigDict(str_strip_whitespace=True)
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="The number of chats to return, up to 100.",
        examples=[20],
    )
    after: str | None = Field(
        default=None,
        max_length=2048,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="The next cursor of the previous list.",
        examples=[
            "WyIyMDI2LTExLTA2VDAwOjAwOjAwWiIsImIzZTFkMzQ5LTFkOGUtNDgxYy04YzY5LTk5ZWE1NzZmOTRjNyJd"
        ],
    )
    before: str | None = Field(
        default=None,
        max_length=2048,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="The previous cursor of the next list.",
        examples=[
            "WyIyMDI2LTExLTA2VDAwOjAwOjAwWiIsImIzZTFkMzQ5LTFkOGUtNDgxYy04YzY5LTk5ZWE1NzZmOTRjNyJd"
        ],
    )

    @field_validator("before")
    @classmethod
    def one_cursor(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is not None and info.data.get("after") is not None:
            raise ValueError("Use after or before, not both.")
        return value


class Paging(Schema):
    limit: int
    next_cursor: str | None
    previous_cursor: str | None
    total: int
    total_capped: bool


class ChatListResponse(Schema):
    items: list[ChatSummary]
    paging: Paging
