"""Schema-derived feature resources registered by each feature's tools file."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, cast
from uuid import UUID

from mcp.shared.exceptions import MCPError
from mcp.types import (
    INVALID_PARAMS,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    TextResourceContents,
)
from pydantic import BaseModel

from app.core.errors import ApiError
from app.core.permissions import has_permission

if TYPE_CHECKING:
    from app.core.tools import ToolContext

JSON_TYPE = "application/json"


@dataclass(frozen=True)
class _Feature:
    feature: str
    one: str
    permission: str
    input_model: type[BaseModel]
    read: Callable[[UUID, ToolContext], dict[str, object]]


_FEATURES: dict[str, _Feature] = {}


def define_feature_resources(
    *,
    feature: str,
    one: str,
    permission: str,
    input_model: type[BaseModel],
    read: Callable[[UUID, ToolContext], dict[str, object]],
) -> None:
    if feature in _FEATURES:
        raise ValueError(f"Duplicate resources: {feature}")
    _FEATURES[feature] = _Feature(feature, one, permission, input_model, read)


def _field_guide(feature: _Feature) -> list[dict[str, object]]:
    document = feature.input_model.model_json_schema(by_alias=False)
    fields: list[dict[str, object]] = []
    for name, field in document["properties"].items():
        schema = field
        if "anyOf" in schema:
            schema = next(
                part for part in schema["anyOf"] if part.get("type") != "null"
            )
        if "$ref" in schema:
            schema = document["$defs"][schema["$ref"].rsplit("/", 1)[1]]
        entry: dict[str, object] = {
            "name": name,
            "kind": schema.get("type"),
            "required": name in document.get("required", []),
            "description": field.get("description"),
            "example": next(iter(field.get("examples", [])), None),
        }
        if "format" in schema:
            entry["format"] = schema["format"]
        if "enum" in schema:
            entry["allowed_values"] = schema["enum"]
            entry["values_uri"] = f"app://{feature.feature}/fields/{name}/values"
        fields.append(entry)
    return fields


def list_resources(context: ToolContext) -> list[Resource]:
    resources: list[Resource] = []
    for feature in _FEATURES.values():
        if not has_permission(context.account.role, feature.permission):
            continue
        resources.append(
            Resource(
                name=f"{feature.feature} fields",
                uri=f"app://{feature.feature}/fields",
                description=f"Read the fields, examples and allowed values for {feature.feature}.",
                mime_type=JSON_TYPE,
            )
        )
        for field in _field_guide(feature):
            if "values_uri" in field:
                resources.append(
                    Resource(
                        name=f"{feature.feature} {field['name']} values",
                        uri=str(field["values_uri"]),
                        description=f"Read the allowed {field['name']} values and their labels for {feature.feature}.",
                        mime_type=JSON_TYPE,
                    )
                )
    return resources


def list_resource_templates(context: ToolContext) -> list[ResourceTemplate]:
    return [
        ResourceTemplate(
            name=f"{feature.feature} item",
            uri_template=f"app://{feature.feature}/{{{feature.one.replace('-', '_')}_id}}",
            description=f"Read every field of one {feature.one} in your organisation.",
            mime_type=JSON_TYPE,
        )
        for feature in _FEATURES.values()
        if has_permission(context.account.role, feature.permission)
    ]


def _failure(kind: str, message: str, retryable: bool = False) -> MCPError:
    return MCPError(
        -32002, message, {"kind": kind, "message": message, "retryable": retryable}
    )


def _read_item(
    feature: _Feature, item_id: UUID, context: ToolContext
) -> dict[str, object]:
    if context.session_factory is None:
        return feature.read(item_id, context)
    with context.session_factory() as db:
        return feature.read(item_id, replace(context, db=db))


async def read_resource(uri: str, context: ToolContext) -> ReadResourceResult:
    feature = next(
        (
            entry
            for entry in _FEATURES.values()
            if uri.startswith(f"app://{entry.feature}/")
        ),
        None,
    )
    if feature is None:
        raise MCPError(
            INVALID_PARAMS, "Unknown resource. Use resources/list to find a resource."
        )
    if not has_permission(context.account.role, feature.permission):
        raise _failure(
            "not_allowed",
            "Your agent account's role cannot view this feature. An admin can change its role on the Members screen.",
        )
    path = uri.removeprefix(f"app://{feature.feature}/")
    data: object
    if path == "fields":
        data = {"fields": _field_guide(feature)}
    elif path.startswith("fields/"):
        field = next(
            (
                field
                for field in _field_guide(feature)
                if field.get("values_uri") == uri
            ),
            None,
        )
        if field is None:
            raise MCPError(
                INVALID_PARAMS,
                "Unknown field values. Read the field guide to find the address.",
            )
        data = {
            "values": [
                {
                    "value": value,
                    "label": str(value)[:1].upper()
                    + str(value)[1:].replace("-", " ").replace("_", " "),
                }
                for value in cast(list[object], field["allowed_values"])
            ]
        }
    else:
        try:
            item_id = UUID(path)
        except ValueError:
            raise MCPError(
                INVALID_PARAMS, "Use a valid item id from the feature search tool."
            ) from None
        try:
            data = await asyncio.to_thread(_read_item, feature, item_id, context)
        except ApiError as error:
            if error.status_code < 500:
                kind = (
                    "not_found"
                    if error.status_code == 404
                    else "not_allowed"
                    if error.status_code == 403
                    else "invalid_input"
                )
                message = (
                    "No item has this id in your organisation. Use the feature search tool to find it."
                    if error.status_code == 404
                    else "Your account cannot read this item. Check its permissions and try again."
                )
                raise _failure(kind, message) from None
            if context.report_error is not None:
                context.report_error(error)
            raise _failure(
                "unavailable",
                "The app could not read this item. Wait 5 seconds and try again.",
                True,
            ) from None
        except Exception as error:  # noqa: BLE001
            if context.report_error is not None:
                context.report_error(error)
            raise _failure(
                "unavailable",
                "The app could not read this item. Wait 5 seconds and try again.",
                True,
            ) from None
    return ReadResourceResult(
        contents=[
            TextResourceContents(
                uri=uri,
                mime_type=JSON_TYPE,
                text=json.dumps(data, ensure_ascii=False),
            )
        ]
    )
