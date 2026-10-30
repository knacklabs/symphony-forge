"""Render generated contracts for Python starter features."""
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


def _schema_source(
    fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any]
) -> str:
    from forge.feature_python import (
        STARTER_PYTHON,
        _field_attr,
        _literal,
        _pydantic_type,
        _python_rename,
        _remove_marks,
        _replace_mark,
        _words,
    )

    definitions = kinds["kinds"]
    imports = [
        "from datetime import date, datetime"
        if any(field["kind"] == "date" for field in fields)
        else "from datetime import datetime",
        "from typing import Literal",
        "from uuid import UUID",
        "",
        "from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator",
        "from pydantic.alias_generators import to_camel",
    ]
    input_fields = []
    for field in fields:
        kind, attr = field["kind"], _field_attr(field)
        optional = field.get("optional", False) and kind != "yes-no"
        definition = definitions[kind]
        sample = definition["sample"]
        if kind == "status" and sample not in field["options"]:
            sample = field["options"][0]
        metadata = [
            f"description={_literal(_words(field['name']) + '.')}",
            f"examples=[{_literal(sample)}]",
        ]
        constraints = []
        if kind == "text":
            constraints.extend(["min_length=1", "max_length=200"])
        elif kind == "long-text":
            constraints.append("max_length=10000")
        elif kind == "email":
            constraints.extend(["max_length=254", 'pattern=r"^[^@\\s]+@[^@\\s]+$"'])
        elif kind in ("number", "money"):
            constraints.append('pattern=r"^-?\\d{1,15}(?:\\.\\d{1,4})?$"')
        if kind == "status":
            suffix = " | None" if optional else ""
            default = "default=None" if optional else f"default={_literal(field['options'][0])}"
            input_fields.append(f"{attr}: Literal[")
            input_fields.extend(f"    {_literal(value)}," for value in field["options"])
            input_fields.append(
                f"]{suffix} = Field({default}, " + ", ".join(metadata) + ")"
            )
        else:
            type_name = definitions[kind]["pydantic"]
            if optional:
                type_name += " | None"
            arguments = metadata + constraints
            if optional:
                arguments.insert(0, "default=None")
            elif kind == "yes-no":
                arguments.insert(0, "default=False")
            input_fields.append(f"{attr}: {type_name} = Field(")
            input_fields.extend(f"    {argument}," for argument in arguments)
            input_fields.append(")")
    response_fields = []
    for field in fields:
        kind, attr = field["kind"], _field_attr(field)
        type_name = _pydantic_type(field, definitions)
        if field.get("optional") and kind != "yes-no":
            type_name += " | None"
        if kind == "status":
            response_fields.append(f"{attr}: Literal[")
            response_fields.extend(f"    {_literal(value)}," for value in field["options"])
            suffix = " | None" if field.get("optional") else ""
            response_fields.append(f"]{suffix}")
        elif kind in ("text", "long-text", "email"):
            limits = {
                "text": ["max_length=200"],
                "long-text": ["max_length=10000"],
                "email": ["max_length=254", 'pattern=r"^[^@\\s]+@[^@\\s]+$"'],
            }[kind]
            response_fields.append(f"{attr}: {type_name} = Field(")
            response_fields.extend(f"    {limit}," for limit in limits)
            response_fields.append(")")
        elif kind in ("number", "money"):
            response_fields.append(
                f'{attr}: {type_name} = Field(pattern=r"^-?\\d{{1,15}}(?:\\.\\d{{1,4}})?$")'
            )
        else:
            response_fields.append(f"{attr}: {type_name}")
        if kind == "money":
            response_fields.append(
                f'{attr}_currency: str = Field(pattern=r"^[A-Z]{{3}}$")'
            )
    filter_fields = []
    for field in fields:
        kind, attr = field["kind"], _field_attr(field)
        if not definitions[kind].get("filter_index"):
            continue
        if kind == "status":
            filter_fields.append(f"{attr}: Literal[")
            filter_fields.extend(f"    {_literal(value)}," for value in field["options"])
            filter_fields.append("] | None = None")
        else:
            query_type = 'Literal["yes", "no"]' if kind == "yes-no" else "UUID"
            filter_fields.append(f"{attr}: {query_type} | None = None")
    sort_fields = [field for field in fields if field["kind"] != "long-text"]
    sort_names = [field["column"] for field in sort_fields]
    sort_names.extend(["createdAtUtc", "updatedAtUtc"])
    sort_field = ["sort_by: Literal["]
    sort_field.extend(f"    {_literal(value)}," for value in sort_names)
    sort_field.append('] = "updatedAtUtc"')
    template = (STARTER_PYTHON / "apps/api/app/projects/schema.py").read_text(
        encoding="utf-8"
    )
    template = _python_rename(template, one, plural)
    search_field = next(field for field in fields if field["kind"] in ("text", "email"))
    template = template.replace(
        "# Search reads the first text or email field: name.",
        f"# Search reads the first text or email field: {_field_attr(search_field)}.",
    )
    template = template.replace(
        "# A cursor holds a whole project name, which can be 120 characters of any script.",
        "# A cursor holds one sort value and the item's id.",
    )
    for name, body in (
        ("schema-imports", imports),
        ("status-type", []),
        ("input-fields", input_fields),
        ("response-fields", response_fields),
        ("filter-fields", filter_fields),
        ("sort-fields", sort_field),
    ):
        template = _replace_mark(template, name, "\n".join(body))
    return _remove_marks(template)
