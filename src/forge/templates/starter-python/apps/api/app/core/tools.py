"""The in-process registry and call boundary for feature MCP tools."""

import asyncio
import json
import re
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from copy import copy
from dataclasses import dataclass, replace
from enum import Enum
from types import GenericAlias, UnionType
from typing import Any, Literal, Protocol, TypeVar, Union, cast, get_args, get_origin
from uuid import UUID

from mcp.shared.exceptions import MCPError
from mcp.types import INVALID_PARAMS, CallToolResult, TextContent, Tool, ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model
from pydantic.fields import FieldInfo
from sqlalchemy.orm import Session as DbSession

from app.core.errors import ApiError
from app.core.permissions import FeaturePermissions, has_permission
from app.core.principal import AccountPrincipal

ToolErrorKind = Literal[
    "invalid_input",
    "not_found",
    "not_allowed",
    "conflict",
    "rate_limited",
    "unavailable",
]
AfterCreate = Callable[[DbSession, UUID], None]
CreateOperation = Callable[[AfterCreate], UUID]
CreateOnce = Callable[[DbSession, AccountPrincipal, str, str, CreateOperation], UUID]
SessionFactory = Callable[[], AbstractContextManager[DbSession]]
CALL_LIMIT_SECONDS = 10


class ToolError(Exception):
    def __init__(
        self,
        kind: ToolErrorKind,
        message: str,
        retryable: bool = False,
        retry_after_seconds: int | None = None,
        details: object | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.details = details


@dataclass(frozen=True)
class ToolContext:
    account: AccountPrincipal
    delete_and_restore: Sequence[str] = ()
    session_factory: SessionFactory | None = None
    create_once: CreateOnce | None = None
    report_error: Callable[[Exception], None] | None = None
    db: DbSession | None = None


@dataclass(frozen=True)
class ToolResult:
    data: dict[str, object]
    summary: str


InputT = TypeVar("InputT", bound=BaseModel)
RowT_co = TypeVar("RowT_co", bound=BaseModel, covariant=True)
InputT_contra = TypeVar("InputT_contra", bound=BaseModel, contravariant=True)
QueryT_contra = TypeVar("QueryT_contra", bound=BaseModel, contravariant=True)


class _PagingInfo(Protocol):
    @property
    def total(self) -> int: ...

    @property
    def total_capped(self) -> bool: ...

    @property
    def next_cursor(self) -> str | None: ...


class Paging(Protocol[RowT_co]):
    @property
    def items(self) -> Sequence[RowT_co]: ...

    @property
    def paging(self) -> _PagingInfo: ...


class FeatureService(Protocol[InputT_contra, RowT_co, QueryT_contra]):
    def list(
        self, account: AccountPrincipal, query: QueryT_contra, /
    ) -> Paging[RowT_co]: ...

    def get(self, account: AccountPrincipal, item_id: UUID, /) -> RowT_co: ...

    def create(
        self, account: AccountPrincipal, input_data: InputT_contra, /
    ) -> RowT_co: ...

    def update(
        self,
        account: AccountPrincipal,
        item_id: UUID,
        input_data: InputT_contra,
        /,
    ) -> RowT_co: ...

    def delete(self, account: AccountPrincipal, item_id: UUID, /) -> None: ...

    def restore(self, account: AccountPrincipal, item_id: UUID, /) -> RowT_co: ...


Call = Callable[[AccountPrincipal, InputT, ToolContext], ToolResult]


@dataclass(frozen=True)
class _Definition:
    tool: Tool
    permission: str
    feature: str
    switched: bool
    invoke: Callable[[object, ToolContext], ToolResult]
    not_found_message: str | None
    api: str | None
    label: str | None


_TOOLS: dict[str, _Definition] = {}


class _StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )


class _ToolErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: ToolErrorKind
    message: str
    retryable: bool
    retry_after_seconds: int | None = None
    details: object | None = None


def _error_schema(output_schema: dict[str, object]) -> dict[str, object]:
    properties = output_schema.get("properties", {})
    success = dict(output_schema)
    failure = {
        "type": "object",
        "properties": {
            "error": _ToolErrorBody.model_json_schema(),
        },
        "required": ["error"],
        "additionalProperties": False,
    }
    result: dict[str, object] = {
        "type": "object",
        "properties": {
            **cast(dict[str, object], properties),
            "error": _ToolErrorBody.model_json_schema(),
        },
        "oneOf": [success, failure],
        "additionalProperties": False,
    }
    if "$defs" in output_schema:
        result["$defs"] = output_schema["$defs"]
    return result


def tool_failure(error: ToolError) -> CallToolResult:
    body = _ToolErrorBody(
        kind=error.kind,
        message=error.message,
        retryable=error.retryable,
        retry_after_seconds=error.retry_after_seconds,
        details=error.details,
    ).model_dump(mode="json", exclude_none=True)
    return CallToolResult(
        content=[
            TextContent(
                type="text", text=json.dumps({"error": body}, ensure_ascii=False)
            )
        ],
        structured_content={"error": body},
        is_error=True,
    )


def define_tool[InputT: BaseModel, OutputT: BaseModel](
    name: str,
    permission: str,
    description: str,
    input_model: type[InputT],
    output_model: type[OutputT],
    annotations: ToolAnnotations,
    call: Call[InputT],
    *,
    feature: str | None = None,
    switched: bool = False,
    api: str | None = None,
    label: str | None = None,
    not_found_message: str | None = None,
) -> Tool:
    if name in _TOOLS:
        raise ValueError(f"Duplicate tool: {name}")
    input_model = _strict_model(input_model)
    output_model = _strict_model(output_model)
    output_schema = cast(
        dict[str, object], output_model.model_json_schema(by_alias=False)
    )
    tool = Tool(
        name=name,
        description=description,
        input_schema=cast(Any, input_model.model_json_schema(by_alias=False)),
        output_schema=cast(Any, _error_schema(output_schema)),
        annotations=annotations,
    )

    def invoke(args: object, context: ToolContext) -> ToolResult:
        try:
            parsed = input_model.model_validate(args)
        except ValidationError as error:
            raise _invalid_input(error, input_model) from None
        result = call(context.account, parsed, context)
        try:
            validated = output_model.model_validate(result.data)
        except ValidationError:
            raise RuntimeError(
                "The tool returned data that does not match its output schema."
            ) from None
        return ToolResult(
            data=cast(
                dict[str, object],
                validated.model_dump(mode="json", by_alias=False, exclude_unset=True),
            ),
            summary=result.summary,
        )

    _TOOLS[name] = _Definition(
        tool=tool,
        permission=permission,
        feature=feature or permission.split(".", maxsplit=1)[0],
        switched=switched,
        invoke=invoke,
        not_found_message=not_found_message,
        api=api,
        label=label,
    )
    return tool


def _strict_model[ModelT: BaseModel](model: type[ModelT]) -> type[ModelT]:
    config = cast(
        Any,
        {
            **model.model_config,
            "extra": "forbid",
            "populate_by_name": True,
        },
    )
    return cast(
        type[ModelT],
        type(
            f"{model.__name__}Strict",
            (model,),
            {"__module__": model.__module__, "model_config": config},
        ),
    )


def list_tools(context: ToolContext) -> list[Tool]:
    return [
        definition.tool
        for definition in _TOOLS.values()
        if has_permission(context.account.role, definition.permission)
        and (
            not definition.switched or definition.feature in context.delete_and_restore
        )
    ]


async def call_tool(name: str, args: object, context: ToolContext) -> CallToolResult:
    definition = _TOOLS.get(name)
    if definition is None:
        raise MCPError(INVALID_PARAMS, "Unknown tool. Use tools/list to find a tool.")
    if not has_permission(context.account.role, definition.permission):
        return tool_failure(
            ToolError(
                "not_allowed",
                f"Your agent account's role cannot use {name}. An admin can change its role on the Members screen.",
            )
        )
    if definition.switched and definition.feature not in context.delete_and_restore:
        return tool_failure(
            ToolError(
                "not_allowed",
                f"An admin has not turned on delete and restore of {definition.feature} for agents. Ask an admin to turn it on in Agent access on the {definition.feature} list.",
            )
        )
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_tool, definition, args, context),
            timeout=CALL_LIMIT_SECONDS,
        )
        return CallToolResult(
            content=[TextContent(type="text", text=result.summary)],
            structured_content=result.data,
            is_error=False,
        )
    except TimeoutError:
        return tool_failure(
            ToolError(
                "unavailable",
                "The app could not finish this call in time. Wait 5 seconds and try again.",
                retryable=True,
                retry_after_seconds=5,
            )
        )
    except ToolError as error:
        return tool_failure(error)
    except ApiError as error:
        if error.status_code >= 500 and context.report_error is not None:
            context.report_error(error)
        return _api_failure(error, definition)
    except Exception as error:  # noqa: BLE001
        if context.report_error is not None:
            context.report_error(error)
        return tool_failure(
            ToolError(
                "unavailable",
                "The app could not finish this call. Wait 5 seconds and try again.",
                retryable=True,
                retry_after_seconds=5,
            )
        )


def _run_tool(
    definition: _Definition, args: object, context: ToolContext
) -> ToolResult:
    if context.session_factory is None:
        return definition.invoke(args, context)
    with context.session_factory() as db:
        return definition.invoke(args, replace(context, db=db))


def _api_failure(error: ApiError, definition: _Definition) -> CallToolResult:
    if error.status_code >= 500:
        kind: ToolErrorKind = "unavailable"
        message = "The app could not finish this call. Wait 5 seconds and try again."
        retryable = True
        retry_after_seconds: int | None = 5
    else:
        kinds: dict[int, ToolErrorKind] = {
            400: "invalid_input",
            403: "not_allowed",
            404: "not_found",
            409: "conflict",
        }
        kind = kinds.get(error.status_code, "invalid_input")
        message = (
            definition.not_found_message
            if error.status_code == 404 and definition.not_found_message
            else error.message
            if error.status_code == 409
            else "The app could not accept this change. Check the fields and try again."
        )
        retryable = False
        retry_after_seconds = None
    return tool_failure(
        ToolError(
            kind,
            message,
            retryable=retryable,
            retry_after_seconds=retry_after_seconds,
            details=error.details,
        )
    )


def _invalid_input(error: ValidationError, model: type[BaseModel]) -> ToolError:
    details = [
        {
            "field": ".".join(str(part) for part in entry.get("loc", ())),
            "reason": str(entry.get("msg", "Check this field.")),
        }
        for entry in error.errors(include_url=False)
    ]
    example = _example(model)
    return ToolError(
        "invalid_input",
        "The tool input has invalid fields. Use the field rules and try again. "
        f"Example: {json.dumps(example, ensure_ascii=False)}.",
        details=details,
    )


def _example(model: type[BaseModel]) -> dict[str, object]:
    values: dict[str, object] = {}
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue
        values[name] = _example_value(field)
    return values


def _example_value(field: FieldInfo) -> object:
    if field.examples:
        return field.examples[0]
    annotation = field.annotation
    origin = get_origin(annotation)
    if origin is Literal:
        return get_args(annotation)[0]
    if origin is not None:
        options = [
            option for option in get_args(annotation) if option is not type(None)
        ]
        if options:
            annotation = options[0]
    if _is_enum_type(annotation):
        return next(iter(cast(type[Enum], annotation))).value
    if annotation is str:
        return "example"
    if annotation is int:
        return 1
    if annotation is float:
        return 1.0
    if annotation is bool:
        return True
    if annotation is UUID:
        return "00000000-0000-4000-8000-000000000000"
    return "example"


def define_feature_tools[InputT: BaseModel, RowT: BaseModel, QueryT: BaseModel](
    *,
    feature: str,
    one: str,
    permissions: FeaturePermissions,
    input_model: type[InputT],
    output_model: type[RowT],
    query_model: type[QueryT],
    concise: Sequence[str],
    links: Mapping[str, str],
    service: Callable[..., FeatureService[InputT, RowT, QueryT]],
    api: str,
    label: str,
    hide: Sequence[str] = (),
    resolve: Callable[[DbSession, str], object] | None = None,
) -> None:
    feature_name = _snake(feature)
    one_name = _snake(one)
    feature_words = feature.replace("-", " ")
    one_words = one.replace("-", " ")
    id_field = f"{one_name}_id"
    input_fields = input_model.model_fields
    response_fields = output_model.model_fields
    query_fields = query_model.model_fields

    response_fields_for_item: dict[str, tuple[object, object]] = {
        id_field: (
            UUID,
            Field(
                description=f"The {one_words} id.",
                examples=["b3e1d349-1d8e-481c-8c69-99ea576f94c7"],
            ),
        ),
        "updated_at_utc": (
            str,
            Field(description="When this item last changed."),
        ),
    }
    for field_name, input_field in input_fields.items():
        output_field = response_fields.get(field_name, input_field)
        annotation = (
            output_field.annotation if output_field.annotation is not None else object
        )
        is_visible = field_name in concise or field_name in links
        optional = _optional(annotation)
        value_info = copy(output_field)
        if not is_visible:
            value_info.default = None
        response_fields_for_item[_snake(field_name)] = (
            annotation if is_visible else optional,
            value_info,
        )
        if _enum_values(annotation):
            is_nullable = type(None) in get_args(annotation)
            label_info = Field(description=f"The display label for {field_name}.")
            if not is_visible or not output_field.is_required():
                label_info.default = None
            response_fields_for_item[f"{_snake(field_name)}_label"] = (
                str
                if is_visible and output_field.is_required() and not is_nullable
                else str | None,
                label_info,
            )
    for field_name in links:
        response_fields_for_item[f"{_snake(field_name.removesuffix('_id'))}_name"] = (
            str | None,
            Field(default=None, description=f"The name of the linked {field_name}."),
        )
    for field_name, field in response_fields.items():
        if field_name in {
            "created_at_utc",
            "created_by_email",
            "modified_by_email",
            "deleted_at_utc",
            "deleted_by_email",
        }:
            response_fields_for_item[field_name] = (
                _optional(field.annotation),
                Field(default=None, description=field.description),
            )
    item_output = _make_model(f"{one_name.title()}ToolOutput", response_fields_for_item)

    search_fields: dict[str, tuple[object, object]] = {}
    for field_name, field in query_fields.items():
        if field_name in {
            "search",
            "deleted",
            "limit",
            "sort_by",
            "sort_order",
            "after",
            "before",
        }:
            continue
        search_fields[_snake(field_name)] = _field_spec(field)
    search_field = query_fields.get("search")
    search_fields["query"] = (
        _field_spec(search_field)
        if search_field is not None
        else (
            str | None,
            Field(
                default=None,
                max_length=200,
                description=f"Text to find in {feature_words}.",
            ),
        )
    )
    search_fields["include_deleted"] = (
        bool,
        Field(
            default=False,
            description="Include deleted items when your role can restore them.",
            examples=[False],
        ),
    )
    sort_options = tuple(
        _snake(str(value)) for value in _enum_values(query_fields["sort_by"].annotation)
    )
    sort_literal = Literal.__getitem__(sort_options)
    search_fields["sort_by"] = (
        sort_literal,
        Field(
            default="updated_at_utc",
            description="The field used to sort results.",
            examples=["updated_at_utc"],
        ),
    )
    search_fields["sort_order"] = (
        Literal["asc", "desc"],
        Field(default="desc", description="The sort direction.", examples=["desc"]),
    )
    search_fields["limit"] = (
        int,
        Field(
            default=20,
            ge=1,
            le=100,
            description="Results per page, from 1 to 100.",
            examples=[20],
        ),
    )
    after_field = query_fields.get("after")
    search_fields["cursor"] = (
        _field_spec(after_field)
        if after_field is not None
        else (
            str | None,
            Field(default=None, description="The next_cursor from the previous page."),
        )
    )
    cursor_info = cast(FieldInfo, search_fields["cursor"][1])
    cursor_info.description = (
        "The next_cursor from the previous page. Omit it for the first page."
    )
    cursor_info.examples = [None]
    search_fields["response_format"] = (
        Literal["concise", "detailed"],
        Field(
            default="concise",
            description="Use detailed to include every useful field and audit email.",
            examples=["concise"],
        ),
    )
    search_input = _make_model(f"{feature_name.title()}SearchInput", search_fields)

    id_fields: dict[str, tuple[object, object]] = {
        id_field: (
            UUID,
            Field(
                description=f"The {one_words} id returned by {feature_name}_search.",
                examples=["b3e1d349-1d8e-481c-8c69-99ea576f94c7"],
            ),
        ),
        "response_format": (
            Literal["concise", "detailed"],
            Field(
                default="concise",
                description="Use detailed to include every useful field and audit email.",
                examples=["concise"],
            ),
        ),
    }
    id_input = _make_model(f"{feature_name.title()}IdInput", id_fields)

    create_fields = {name: _field_spec(field) for name, field in input_fields.items()}
    create_fields["idempotency_key"] = (
        str | None,
        Field(
            default=None,
            min_length=1,
            max_length=200,
            description="Reuse this key to retry without creating another item.",
            examples=["create-item-1"],
        ),
    )
    create_fields["response_format"] = id_fields["response_format"]
    create_input = _make_model(f"{feature_name.title()}CreateInput", create_fields)
    update_fields = {
        **{name: _field_spec(field) for name, field in input_fields.items()},
        **id_fields,
    }
    update_input = _make_model(f"{feature_name.title()}UpdateInput", update_fields)

    search_output = _make_model(
        f"{feature_name.title()}SearchOutput",
        {
            "items": (GenericAlias(list, item_output), Field()),
            "total": (int, Field()),
            "total_is_capped": (bool, Field()),
            "next_cursor": (str | None, Field()),
        },
    )
    delete_output = _make_model(
        f"{feature_name.title()}DeleteOutput",
        {id_field: (UUID, Field()), "deleted": (Literal[True], Field())},
    )

    descriptions = {
        "search": f"Find {feature_words} in your organisation by text and filters. Use this first when you need an id for {feature_name}_get, {feature_name}_update or {feature_name}_delete; it returns 20 results by default and accepts next_cursor as cursor.",
        "get": f"Read one {one_words} with its useful fields, or every field with response_format detailed. Use {feature_name}_search first when you do not know the {id_field}.",
        "create": f"Create a {one_words} in your organisation. Use idempotency_key to retry safely, then {feature_name}_get to read it.",
        "update": f"Replace the editable fields of one {one_words}. Use {feature_name}_get first to read its current fields; repeating the same update makes no extra change.",
        "delete": f"Soft delete one {one_words} and keep its history. Use {feature_name}_search to find it and {feature_name}_restore to bring it back.",
        "restore": f"Restore a deleted {one_words}. Use {feature_name}_search with include_deleted to find it; repeating restore makes no extra change.",
    }
    actions = ("search", "get", "create", "update", "delete", "restore")
    for action in actions:
        if action in hide:
            continue
        permission = getattr(
            permissions,
            "view"
            if action in {"search", "get"}
            else "edit"
            if action == "update"
            else action,
        )
        input_type = {
            "search": search_input,
            "get": id_input,
            "create": create_input,
            "update": update_input,
            "delete": id_input,
            "restore": id_input,
        }[action]
        output_type = (
            search_output
            if action == "search"
            else delete_output
            if action == "delete"
            else item_output
        )
        annotations = ToolAnnotations(
            title=f"{action.title()} {feature_words if action == 'search' else one_words}",
            read_only_hint=action in {"search", "get"},
            destructive_hint=action == "delete",
            idempotent_hint=action in {"update", "delete", "restore"},
            open_world_hint=False,
        )
        define_tool(
            name=f"{feature_name}_{action}",
            feature=feature,
            permission=permission,
            description=descriptions[action],
            input_model=input_type,
            output_model=output_type,
            annotations=annotations,
            switched=action in {"delete", "restore"},
            api=api,
            label=label,
            not_found_message=f"No {one_words} has this {id_field} in your organisation. Use {feature_name}_search to find it.",
            call=_feature_call(
                action,
                feature=feature,
                one=one,
                id_field=id_field,
                input_model=input_model,
                query_model=query_model,
                concise=concise,
                links=links,
                service=service,
                label=label,
                resolve=resolve,
            ),
        )


def _feature_call[InputT: BaseModel, QueryT: BaseModel, RowT: BaseModel](
    action: str,
    *,
    feature: str,
    one: str,
    id_field: str,
    input_model: type[InputT],
    query_model: type[QueryT],
    concise: Sequence[str],
    links: Mapping[str, str],
    service: Callable[..., FeatureService[InputT, RowT, QueryT]],
    label: str,
    resolve: Callable[[DbSession, str], object] | None,
) -> Call[BaseModel]:
    feature_name = _snake(feature)
    one_words = one.replace("-", " ")
    id_fields = input_model.model_fields
    query_fields = query_model.model_fields

    def call(
        account: AccountPrincipal, args: BaseModel, context: ToolContext
    ) -> ToolResult:
        if context.db is None:
            raise RuntimeError("The MCP tool has no database session.")
        db = context.db
        values = args.model_dump(mode="python", by_alias=False)
        item_id = cast(UUID, values.get(id_field))
        response_format = values.get("response_format", "concise")
        detailed = response_format == "detailed"
        feature_service = service(db)
        if action == "search":
            query_values: dict[str, object] = {
                name: values[_snake(name)]
                for name in query_fields
                if name
                not in {
                    "search",
                    "deleted",
                    "limit",
                    "sort_by",
                    "sort_order",
                    "after",
                    "before",
                }
                and _snake(name) in values
            }
            query_values.update(
                {
                    "search": values.get("query"),
                    "deleted": "yes" if values.get("include_deleted") else None,
                    "limit": values.get("limit", 20),
                    "sort_by": _native_sort(
                        str(values.get("sort_by", "updated_at_utc")),
                        query_fields["sort_by"].annotation,
                    ),
                    "sort_order": values.get("sort_order", "desc"),
                    "after": values.get("cursor"),
                    "before": None,
                }
            )
            query = query_model.model_validate(query_values)
            page = feature_service.list(account, query)
            paging = page.paging
            total = paging.total
            total_capped = paging.total_capped
            next_cursor = paging.next_cursor
            link_cache: dict[tuple[str, str], str | None] = {}
            items = [
                _item(
                    row,
                    account,
                    context,
                    id_field,
                    input_model,
                    concise,
                    links,
                    detailed,
                    resolve,
                    link_cache,
                )
                for row in page.items
            ]
            data: dict[str, object] = {
                "items": items,
                "total": total,
                "total_is_capped": total_capped,
                "next_cursor": next_cursor,
            }
            shown_total = "more than 10,000" if total_capped else f"{total:,}"
            summary = f"Showing {len(items)} of {shown_total} matching {feature.replace('-', ' ')}."
            filter_fields = [
                _snake(name)
                for name in query_fields
                if name
                not in {
                    "search",
                    "deleted",
                    "limit",
                    "sort_by",
                    "sort_order",
                    "after",
                    "before",
                }
            ]
            if next_cursor:
                summary += " Pass next_cursor as cursor for more, or narrow with query"
                if filter_fields:
                    summary += " or " + ", ".join(filter_fields)
                summary += "."
            return ToolResult(data=data, summary=summary)

        if action == "create":
            input_values = {name: values.get(_snake(name)) for name in id_fields}
            input_data = input_model.model_validate(input_values)
            idempotency_key = values.get("idempotency_key")
            if idempotency_key:
                if context.create_once is None:
                    raise RuntimeError("The MCP tool has no idempotency service.")

                def create(after_create: AfterCreate) -> UUID:
                    created = service(db, after_create=after_create).create(
                        account, input_data
                    )
                    return cast(
                        UUID,
                        created.model_dump(mode="python", by_alias=False)["id"],
                    )

                item_id = context.create_once(
                    db, account, f"{feature_name}_create", str(idempotency_key), create
                )
                row = feature_service.get(account, item_id)
            else:
                row = feature_service.create(account, input_data)
            summary = f"Created the {one_words} {_label(row, label)}."
        elif action == "update":
            input_data = input_model.model_validate(
                {name: values.get(_snake(name)) for name in id_fields}
            )
            row = feature_service.update(account, item_id, input_data)
            summary = f"Updated the {one_words} {_label(row, label)}."
        elif action == "delete":
            row = feature_service.get(account, item_id)
            if getattr(row, "deleted_at_utc", None) is None:
                feature_service.delete(account, item_id)
            return ToolResult(
                data={id_field: item_id, "deleted": True},
                summary=f"Deleted the {one_words} {_label(row, label)}.",
            )
        elif action == "restore":
            row = feature_service.get(account, item_id)
            if getattr(row, "deleted_at_utc", None) is not None:
                row = feature_service.restore(account, item_id)
            summary = f"Restored the {one_words} {_label(row, label)}."
        else:
            row = feature_service.get(account, item_id)
            summary = f"{_first_upper(one_words)} {_label(row, label)}."
        return ToolResult(
            data=_item(
                row,
                account,
                context,
                id_field,
                input_model,
                concise,
                links,
                detailed,
                resolve,
                {},
            ),
            summary=summary,
        )

    return call


def _item[RowT: BaseModel, InputT: BaseModel](
    row: RowT,
    account: AccountPrincipal,
    context: ToolContext,
    id_field: str,
    input_model: type[InputT],
    concise: Sequence[str],
    links: Mapping[str, str],
    detailed: bool,
    resolve: Callable[[DbSession, str], object] | None,
    link_cache: dict[tuple[str, str], str | None],
) -> dict[str, object]:
    source = cast(dict[str, object], row.model_dump(mode="json", by_alias=False))
    result: dict[str, object] = {
        id_field: source["id"],
        "updated_at_utc": source["updated_at_utc"],
    }
    for field_name, field in input_model.model_fields.items():
        if not detailed and field_name not in concise and field_name not in links:
            continue
        value = source.get(field_name)
        result[_snake(field_name)] = value
        if _enum_values(field.annotation):
            result[f"{_snake(field_name)}_label"] = (
                _title(str(value)) if value is not None else None
            )
    for field_name, token in links.items():
        linked_id = source.get(field_name)
        result[f"{_snake(field_name.removesuffix('_id'))}_name"] = _linked_name(
            account, context, resolve, token, linked_id, link_cache
        )
    if detailed:
        for field_name in (
            "created_at_utc",
            "created_by_email",
            "modified_by_email",
            "deleted_at_utc",
            "deleted_by_email",
        ):
            if field_name in source:
                result[field_name] = source[field_name]
    return result


def _linked_name(
    account: AccountPrincipal,
    context: ToolContext,
    resolve: Callable[[DbSession, str], object] | None,
    token: str,
    linked_id: object,
    cache: dict[tuple[str, str], str | None],
) -> str | None:
    if linked_id is None:
        return None
    cache_key = (token, str(linked_id))
    if cache_key in cache:
        return cache[cache_key]
    if resolve is None:
        raise RuntimeError("A linked tool needs its target service.")
    definition = next(
        (
            candidate
            for candidate in _TOOLS.values()
            if candidate.api == token and candidate.permission.endswith(".view")
        ),
        None,
    )
    if definition is None:
        raise RuntimeError("The linked feature has no public view tool.")
    if not has_permission(account.role, definition.permission):
        cache[cache_key] = None
        return None
    if context.db is None:
        raise RuntimeError("The MCP tool has no database session.")
    linked_service = resolve(context.db, token)
    getter = getattr(linked_service, "get", None)
    if getter is None:
        raise RuntimeError("A linked feature must expose its public get service.")
    try:
        linked = getter(account, UUID(str(linked_id)))
    except ApiError as error:
        if error.status_code in {403, 404}:
            cache[cache_key] = None
            return None
        raise
    display_field = next(
        (
            definition.label
            for definition in _TOOLS.values()
            if definition.api == token and definition.label is not None
        ),
        None,
    )
    if display_field is None:
        raise RuntimeError("The linked feature has no display field.")
    name = cast(str | None, getattr(linked, display_field, None))
    cache[cache_key] = name
    return name


def _label(row: BaseModel, field_name: str) -> str:
    return str(getattr(row, field_name))


def _make_model(
    name: str, fields: Mapping[str, tuple[object, object]]
) -> type[BaseModel]:
    return cast(
        type[BaseModel],
        create_model(
            name,
            __base__=_StrictModel,
            **cast(dict[str, Any], dict(fields)),
        ),
    )


def _field_spec(field: FieldInfo) -> tuple[object, object]:
    field_info = copy(field)
    field_info.alias = None
    field_info.validation_alias = None
    field_info.serialization_alias = None
    return field.annotation if field.annotation is not None else object, field_info


def _enum_values(annotation: object) -> tuple[object, ...]:
    if annotation is None:
        return ()
    if _is_enum_type(annotation):
        return tuple(item.value for item in cast(type[Enum], annotation))
    origin = get_origin(annotation)
    if origin is Literal:
        return get_args(annotation)
    if origin in {Union, UnionType}:
        members = [item for item in get_args(annotation) if item is not type(None)]
        if len(members) == 1:
            return _enum_values(members[0])
    return ()


def _is_enum_type(annotation: object) -> bool:
    if not isinstance(annotation, type):
        return False
    try:
        return issubclass(annotation, Enum)
    except TypeError:
        return False


def _optional(annotation: object) -> object:
    if annotation is None:
        return object | None
    return cast(Any, annotation) | None


def _native_sort(value: str, annotation: object) -> object:
    for option in _enum_values(annotation):
        if _snake(str(option)) == value:
            return option
    return value


def _snake(value: str) -> str:
    return re.sub(r"-", "_", re.sub(r"([A-Z])", r"_\1", value)).lower().lstrip("_")


def _title(value: str) -> str:
    words = value.replace("_", " ").replace("-", " ")
    return words[:1].upper() + words[1:]


def _first_upper(value: str) -> str:
    return value[:1].upper() + value[1:]
