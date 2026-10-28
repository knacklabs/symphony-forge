from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SuccessEnvelope[DataT](BaseModel):
    success: Literal[True] = True
    data: DataT | None
    error: None = None


class FieldError(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    field: str = Field(max_length=128)
    reason: str = Field(max_length=256)


class ErrorDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_errors: list[FieldError] | None = Field(default=None, alias="fieldErrors")


class ApiErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(max_length=64)
    message: str = Field(max_length=300)
    details: ErrorDetails | None
    error_id: UUID = Field(alias="errorId")


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: Literal[False] = False
    data: None = None
    error: ApiErrorBody
