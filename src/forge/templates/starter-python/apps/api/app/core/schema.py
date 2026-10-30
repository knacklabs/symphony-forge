from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    status: str = Field(max_length=16)
