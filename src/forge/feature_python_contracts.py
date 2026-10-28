"""Render the Python starter's generated TypeScript contracts from marked project regions."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from forge.feature_api import _camel, _input_expr, _pascal

STARTER = Path(__file__).parent / "templates/starter-python"
MARKER = re.compile(
    r"(?P<indent>^[ \t]*)(?:// )forge:feature:(?P<name>[\w-]+):start\n"
    r".*?^[ \t]*// forge:feature:(?P=name):end\n?",
    re.M | re.S,
)


def _replace(text: str, name: str, body: str) -> str:
    matches = [match for match in MARKER.finditer(text) if match["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"The Python projects starter needs one {name} feature marker.")
    match = matches[0]
    indent = match["indent"]
    lines = [indent + line if line else "" for line in body.rstrip("\n").splitlines()]
    return text[: match.start()] + "\n".join(lines) + "\n" + text[match.end() :]


def _quote(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


def _column(field: dict[str, Any]) -> str:
    return field["column"]


def _label(name: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("-", " ").lower()


def _status_schema(one: str, field: dict[str, Any]) -> str:
    name = _camel(one) + _pascal(_column(field)) + "Schema"
    return f"export const {name} = z.enum([{', '.join(_quote(option) for option in field['options'])}]);"


def _input_field(field: dict[str, Any], one: str, kinds: dict[str, Any]) -> str:
    return f"{_column(field)}: {_input_expr(field, one, kinds)},"


def _filters(fields: list[dict[str, Any]], one: str, kinds: dict[str, Any]) -> str:
    search = next(field for field in fields if field["kind"] in ("text", "email"))
    lines = [
        "search: z.string().trim().max(200).optional()"
        f".meta({{ description: 'Text to find in the {_label(search['name'])}, up to 200 characters.', "
        "example: 'example' }),"
    ]
    for field in fields:
        kind, column = field["kind"], _column(field)
        if kind == "status":
            expression = _camel(one) + _pascal(column) + "Schema.optional()"
        elif kind == "yes-no":
            expression = "z.enum(['yes', 'no']).optional()"
        elif kind == "link":
            expression = "z.string().uuid().optional()"
        else:
            continue
        lines.append(
            f"{column}: {expression}.meta({{ description: 'Filter by {_label(field['name'])}.' }}),"
        )
    lines.append(
        "deleted: z.enum(['yes']).optional().meta({ description: "
        "'Show deleted items too; only a caller with the restore permission gets them.', example: 'yes' }),"
    )
    return "\n".join(lines)


def render_python_contracts(
    fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any]
) -> str:
    """Return a Zod contract that uses the Python API's generated OpenAPI types."""
    model, item = _pascal(one), _camel(one)
    template = (STARTER / "libs/projects/contracts/src/index.ts").read_text(encoding="utf-8")
    template = re.sub(
        r"projects|Projects|PROJECTS|project|Project|PROJECT",
        lambda match: {
            "projects": _camel(plural),
            "Projects": _pascal(plural),
            "PROJECTS": plural.replace("-", "_").upper(),
            "project": item,
            "Project": model,
            "PROJECT": one.replace("-", "_").upper(),
        }[match[0]],
        template,
    )
    template = _replace(
        template,
        "status-schema",
        "\n".join(_status_schema(one, field) for field in fields if field["kind"] == "status"),
    )
    template = _replace(
        template,
        "schema-fields",
        "\n".join(_input_field(field, one, kinds) for field in fields),
    )
    template = _replace(template, "filters", _filters(fields, one, kinds))
    sortable = [field["column"] for field in fields if field["kind"] != "long-text"]
    if not any(field["kind"] == "text" and not field.get("optional") for field in fields):
        raise ValueError("The feature needs a required text field for its display name.")
    sortable.extend(["createdAtUtc", "updatedAtUtc"])
    sort_field = (
        f"sortBy: z.enum([{', '.join(_quote(value) for value in sortable)}]).default('updatedAtUtc')"
        ".meta({ description: 'The field used to sort the list.', example: 'updatedAtUtc' }),"
    )
    template = _replace(template, "sort-fields", sort_field)
    template = _replace(
        template, "sort-type", f'export type {model}SortBy = {model}ListQuery["sortBy"];'
    )
    statuses = []
    for field in fields:
        if field["kind"] != "status":
            continue
        column = _column(field)
        status_type = _pascal(one) + _pascal(column)
        statuses.append(
            f"export type {status_type} = Exclude<components['schemas']['{model}']['{column}'], null | undefined>;"
        )
    status_types = "\n".join(statuses)
    template = _replace(template, "status-type", status_types)
    plural_var = _camel(plural)
    return template.replace(f"@app/{plural_var}-", f"@app/{plural}-")
