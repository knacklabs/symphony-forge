from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.core import Role


class AuthSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


Email = Annotated[str, Field(max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")]


class CredentialsInput(AuthSchema):
    email: Email
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class ForgotPasswordInput(AuthSchema):
    email: Email

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class ResetPasswordInput(AuthSchema):
    token: str = Field(min_length=32, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class AcceptInviteInput(CredentialsInput):
    token: str = Field(
        min_length=32,
        max_length=256,
        description="The single-use token from the invite link.",
        examples=["abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG"],
    )


class Account(AuthSchema):
    id: UUID
    email: Email
    role: Role
    permissions: list[str] = Field(
        description="What the account's role may do, such as projects.delete.",
        examples=[["projects.view", "projects.create"]],
    )


class AuthOptions(AuthSchema):
    sign_up_open: bool = Field(
        description="Whether anyone can create an account.", examples=[True]
    )


class MessageResponse(AuthSchema):
    message: str = Field(max_length=200)


class SessionData(AuthSchema):
    account: Account
    session_token: str = Field(max_length=64)
    csrf_token: str = Field(max_length=64)
    expires_at_utc: datetime
