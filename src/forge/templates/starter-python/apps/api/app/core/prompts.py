"""Optional repeated tasks declared in a feature's tools file."""

from collections.abc import Callable
from dataclasses import dataclass

from mcp.shared.exceptions import MCPError
from mcp.types import (
    INVALID_PARAMS,
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
)
from pydantic import BaseModel, ValidationError

from app.core.permissions import has_permission
from app.core.tools import ToolContext, _strict_model


@dataclass(frozen=True)
class _Definition:
    prompt: Prompt
    permission: str
    render: Callable[[object], str]


_PROMPTS: dict[str, _Definition] = {}


def define_prompt[InputT: BaseModel](
    *,
    name: str,
    description: str,
    permission: str,
    arguments: type[InputT],
    render: Callable[[InputT], str],
) -> None:
    if name in _PROMPTS:
        raise ValueError(f"Duplicate prompt: {name}")
    model = _strict_model(arguments)

    def render_arguments(args: object) -> str:
        try:
            parsed = model.model_validate(args)
        except ValidationError:
            raise MCPError(
                INVALID_PARAMS,
                "The prompt inputs are invalid. Check its required inputs and try again.",
            ) from None
        return render(parsed)

    _PROMPTS[name] = _Definition(
        prompt=Prompt(
            name=name,
            description=description,
            arguments=[
                PromptArgument(
                    name=field_name,
                    description=field.description,
                    required=field.is_required(),
                )
                for field_name, field in model.model_fields.items()
            ],
        ),
        permission=permission,
        render=render_arguments,
    )


def list_prompts(context: ToolContext) -> list[Prompt]:
    return [
        entry.prompt
        for entry in _PROMPTS.values()
        if has_permission(context.account.role, entry.permission)
    ]


def get_prompt(name: str, args: object, context: ToolContext) -> GetPromptResult:
    entry = _PROMPTS.get(name)
    if entry is None:
        raise MCPError(
            INVALID_PARAMS, "Unknown prompt. Use prompts/list to find a prompt."
        )
    if not has_permission(context.account.role, entry.permission):
        raise MCPError(
            INVALID_PARAMS,
            "Your agent account's role cannot use this prompt. An admin can change its role on the Members screen.",
        )
    return GetPromptResult(
        messages=[
            PromptMessage(
                role="user", content=TextContent(type="text", text=entry.render(args))
            )
        ]
    )
