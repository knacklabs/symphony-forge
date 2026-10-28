"""Render the Python API for a feature from the starter's projects contract."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

STARTER_PYTHON = Path(__file__).parent / "templates/starter-python"
MARKER = re.compile(
    r"(?P<indent>^[ \t]*)# forge:feature:(?P<name>[\w-]+):start\n"
    r".*?^[ \t]*# forge:feature:(?P=name):end\n?",
    re.M | re.S,
)


def _snake(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"-+", "_", value).lower()


def _pascal(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in _snake(value).split("_"))


def _words(value: str) -> str:
    return _snake(value).replace("_", " ").capitalize()


def _sql(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _literal(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def _replace_mark(text: str, name: str, body: str) -> str:
    marker = re.compile(
        rf"(?P<indent>^[ \t]*)# forge:feature:{re.escape(name)}:start\n"
        rf".*?^[ \t]*# forge:feature:{re.escape(name)}:end\n?",
        re.M | re.S,
    )
    matches = list(marker.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"The Python projects starter needs one {name} feature marker.")
    match = matches[0]
    indent = match["indent"]
    lines = [indent + line if line else "" for line in body.rstrip("\n").splitlines()]
    return text[: match.start()] + "\n".join(lines) + "\n" + text[match.end() :]


def _remove_marks(text: str) -> str:
    return re.sub(r"^[ \t]*# forge:feature:[\w-]+:(?:start|end)\n", "", text, flags=re.M)


def _feature_mcp(text: str, include: bool) -> str:
    """Keep MCP-only code for a starter that ships the server."""
    matches = [match for match in MARKER.finditer(text) if match["name"] in {"mcp", "mcp-cases"}]
    for match in reversed(matches):
        lines = match.group(0).splitlines(keepends=True)
        replacement = "".join(lines[1:-1]) if include else ""
        text = text[: match.start()] + replacement + text[match.end() :]
    return text


def _python_rename(text: str, one: str, plural: str) -> str:
    module, singular = _snake(plural), _snake(one)
    text = text.replace("PROJECT_PERMISSIONS", singular.upper() + "_PERMISSIONS")
    text = text.replace("PROJECT_CSV_COLUMNS", module.upper() + "_CSV_COLUMNS")
    for old, new in (
        ("PROJECTS", module.upper()),
        ("PROJECT", singular.upper()),
        ("Projects", _pascal(plural)),
        ("Project", _pascal(one)),
        ("projects", module),
        ("project", singular),
    ):
        text = text.replace(old, new)
    text = text.replace("list_projects", f"list_{module}")
    text = text.replace("export_projects", f"export_{module}")
    text = text.replace("create_project", f"create_{singular}")
    text = text.replace("project_id", f"{singular}_id")
    text = text.replace(f'"/api/v1/{module}', f'"/api/v1/{plural}')
    text = text.replace(f'"{module}.csv"', f'"{plural}.csv"')
    text = text.replace(
        f'"List your organisation’s {module}."',
        f'"List your organisation’s {_words(plural).lower()}."',
    )
    return text


def _table_type(kind: str, definitions: dict[str, Any]) -> str:
    return definitions[kind]["sqlalchemy"].split(", server_default=", 1)[0]


def _value(field: dict[str, Any], definitions: dict[str, Any], key: str) -> str:
    value = definitions[field["kind"]][key]
    return value.replace("{first}", field["options"][0].replace("'", "''")) if field["kind"] == "status" else value


def _table_type_name(kind: str, definitions: dict[str, Any]) -> str:
    return re.match(r"[A-Za-z_][A-Za-z0-9_]*", _table_type(kind, definitions))[0]


def _pydantic_type(field: dict[str, Any], definitions: dict[str, Any]) -> str:
    if field["kind"] == "status":
        return "Literal[" + ", ".join(_literal(value) for value in field["options"]) + "]"
    return definitions[field["kind"]]["pydantic"]


def _field_attr(field: dict[str, Any]) -> str:
    return _snake(field["column"])


def _check_parts(
    field: dict[str, Any], definitions: dict[str, Any], table: str, *, currency: bool = False
) -> tuple[str, str] | None:
    if currency and field["kind"] != "money":
        return None
    check = (
        definitions["money"].get("currency_check", "")
        if currency
        else definitions[field["kind"]].get("check", "")
    )
    if not check:
        return None
    column = _field_attr(field) + "_currency" if currency else _snake(field["column"])
    options = ", ".join(_sql(option) for option in field.get("options", []))
    check = (check.replace("{table}", table).replace("{column}", column)
             .replace("{currency}", column).replace("{options}", options))
    match = re.fullmatch(r'CONSTRAINT "([^"]+)" CHECK \((.*)\)', check)
    if match is None:
        raise ValueError(f"Unsupported check template for {field['kind']}.")
    return match[1], match[2]


def _public_service(root: Path, target: str) -> str:
    module = _snake(target)
    entry = root / "apps/api/app" / module / "__init__.py"
    source = entry.read_text(encoding="utf-8")
    match = re.search(rf"from app\.{re.escape(module)}\.service import ([A-Za-z_]\w*Service)\b", source)
    exports = re.search(r"__all__\s*=\s*\[([^]]*)\]", source, re.S)
    if match is None or exports is None or match[1] not in ast.literal_eval("[" + exports[1] + "]"):
        raise ValueError(f"The linked feature {target!r} does not export its public service.")
    return match[1]


def _model_source(
    fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any]
) -> str:
    definitions = kinds["kinds"]
    table, schema = _snake(one), _snake(plural)
    used_types = {_table_type_name(field["kind"], definitions) for field in fields}
    if any(field["kind"] == "money" for field in fields):
        used_types.add(definitions["money"]["currency_sqlalchemy"])
    imports = {"DateTime", "ForeignKey", "Index", "func", "text"} | used_types
    if any(
        _check_parts(field, definitions, table)
        or _check_parts(field, definitions, table, currency=True)
        for field in fields
    ):
        imports.add("CheckConstraint")
    if any(", server_default=false()" in _value(field, definitions, "sqlalchemy") for field in fields):
        imports.add("false")
    import_lines = [
        "from datetime import date, datetime"
        if any(field["kind"] == "date" for field in fields)
        else "from datetime import datetime"
    ]
    if any(field["kind"] in ("number", "money") for field in fields):
        import_lines.append("from decimal import Decimal")
    import_lines.extend(["from uuid import UUID", "", "from sqlalchemy import ("])
    import_lines.extend(f"    {name}," for name in sorted(imports))
    import_lines.extend(
        [
            ")",
            "from sqlalchemy.orm import Mapped, mapped_column",
            "",
            "from app.core import Base",
        ]
    )
    table_args = []
    for field in fields:
        for check in (
            _check_parts(field, definitions, table),
            _check_parts(field, definitions, table, currency=True),
        ):
            if not check:
                continue
            table_args.extend(
                [
                    "CheckConstraint(",
                    f"    {_literal(check[1])},",
                    f"    name={_literal(check[0])},",
                    "),",
                ]
            )
    for column in (
        "organisation_id",
        "created_by_account_id",
        "modified_by_account_id",
        "deleted_by_account_id",
    ):
        table_args.extend(
            ["Index(", f'    "idx_{table}_{column}",', f'    "{column}",', "),"]
        )
    table_args.extend(
        [
            "Index(",
            f'    "idx_{table}_list",',
            '    "organisation_id",',
            '    text("updated_at_utc DESC"),',
            '    text("id DESC"),',
            '    postgresql_where=text("deleted_at_utc IS NULL"),',
            "),",
        ]
    )
    for field in fields:
        kind, column = definitions[field["kind"]], _snake(field["column"])
        if kind.get("filter_index"):
            table_args.extend(
                [
                    "Index(",
                    f'    "idx_{table}_{column}",',
                    '    "organisation_id",',
                    f'    "{column}",',
                    '    text("updated_at_utc DESC"),',
                    '    text("id DESC"),',
                    '    postgresql_where=text("deleted_at_utc IS NULL"),',
                    "),",
                ]
            )
        if kind.get("search_index"):
            table_args.extend(
                [
                    "Index(",
                    f'    "idx_{table}_{column}_search",',
                    '    "organisation_id",',
                    f'    "{column}",',
                    '    postgresql_using="gin",',
                    '    postgresql_ops={',
                    '        "organisation_id": "uuid_ops",',
                    f'        "{column}": "gin_trgm_ops",',
                    '    },',
                    '    postgresql_where=text("deleted_at_utc IS NULL"),',
                    "),",
                ]
            )
        if kind.get("index"):
            table_args.extend(
                [
                    "Index(",
                    f'    "idx_{table}_{column}_fk",',
                    f'    "{column}",',
                    "),",
                ]
            )
    table_args.append(f'{{"schema": "{schema}"}},')
    model_fields = []
    for field in fields:
        kind, attr = field["kind"], _field_attr(field)
        optional = field.get("optional", False) and kind != "yes-no"
        base = "Decimal" if kind in ("number", "money") else definitions[kind]["pydantic"]
        if optional:
            base += " | None"
        column_type = _table_type(kind, definitions)
        if optional and kind == "status":
            # Persist an explicit None instead of letting the server default replace it.
            column_type += "().evaluates_none()"
        args = [column_type, f"nullable={optional}"]
        server_default = _value(field, definitions, "sqlalchemy").partition(", server_default=")[2]
        if server_default:
            args.append(f"server_default={server_default}")
        model_fields.append(f"{attr}: Mapped[{base}] = mapped_column(")
        model_fields.extend(f"    {arg}," for arg in args)
        model_fields.append(")")
        if kind == "money":
            currency = attr + "_currency"
            currency_type = definitions[kind]["currency_sqlalchemy"]
            model_fields.extend(
                [
                    f"{currency}: Mapped[str] = mapped_column(",
                    f"    {currency_type},",
                    "    nullable=False,",
                    ")",
                ]
            )
    template = (STARTER_PYTHON / "apps/api/app/projects/models.py").read_text(
        encoding="utf-8"
    )
    template = _python_rename(template, one, plural)
    template = _replace_mark(template, "model-imports", "\n".join(import_lines))
    template = _replace_mark(template, "model-table-args", "\n".join(table_args))
    template = _replace_mark(template, "model-fields", "\n".join(model_fields))
    return _remove_marks(template)


def _migration_source(
    fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any],
    root: Path,
) -> tuple[str, str]:
    definitions, table = kinds["kinds"], _snake(one)
    schema = _snake(plural)
    revisions: list[tuple[Path, str, str | None]] = []
    for path in (root / "apps/api/migrations/versions").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in {"revision", "down_revision"}:
                    values[node.targets[0].id] = ast.literal_eval(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id in {"revision", "down_revision"} and node.value is not None:
                    values[node.target.id] = ast.literal_eval(node.value)
        if "revision" in values:
            revisions.append((path, values["revision"], values.get("down_revision")))
    parents = {down for _, _, down in revisions if isinstance(down, str)}
    heads = [(path, revision) for path, revision, _ in revisions if revision not in parents]
    if len(heads) != 1:
        raise ValueError("The Python starter must have one Alembic head before building a feature.")
    next_number = max(int(match[1]) for path, _, _ in revisions
                      if (match := re.match(r"(\d{4})_", path.name))) + 1
    revision = f"{next_number:04d}_{_snake(plural)}"
    down_revision = heads[0][1]
    columns = [
        '    "id" UUID NOT NULL DEFAULT uuidv7()',
        '    "organisation_id" UUID NOT NULL',
    ]
    checks = []
    for field in fields:
        column = _snake(field["column"])
        kind = field["kind"]
        optional = field.get("optional", False) and kind != "yes-no"
        declaration = f'    "{column}" {_value(field, definitions, "sql")}'
        if not optional:
            declaration += " NOT NULL"
        columns.append(declaration)
        check = _check_parts(field, definitions, table)
        if check:
            checks.append(f'    CONSTRAINT "{check[0]}" CHECK ({check[1]})')
        currency_check = _check_parts(field, definitions, table, currency=True)
        if currency_check:
            currency_column = _field_attr(field) + "_currency"
            columns.append(
                f'    "{currency_column}" {definitions[kind]["currency_sql"]} NOT NULL'
            )
            checks.append(
                f'    CONSTRAINT "{currency_check[0]}" CHECK ({currency_check[1]})'
            )
    columns.extend([
        '    "created_at_utc" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP',
        '    "updated_at_utc" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP',
        '    "created_by_account_id" UUID NOT NULL',
        '    "modified_by_account_id" UUID NOT NULL',
        '    "deleted_at_utc" TIMESTAMPTZ',
        '    "deleted_by_account_id" UUID',
    ])
    constraints = [
        f'    CONSTRAINT "{table}_pkey" PRIMARY KEY ("id")',
        *checks,
        f'    CONSTRAINT "{table}_organisation_id_fkey" FOREIGN KEY ("organisation_id") REFERENCES core.organisation("id") ON DELETE RESTRICT',
        f'    CONSTRAINT "{table}_created_by_account_id_fkey" FOREIGN KEY ("created_by_account_id") REFERENCES core.account("id") ON DELETE RESTRICT',
        f'    CONSTRAINT "{table}_modified_by_account_id_fkey" FOREIGN KEY ("modified_by_account_id") REFERENCES core.account("id") ON DELETE RESTRICT',
        f'    CONSTRAINT "{table}_deleted_by_account_id_fkey" FOREIGN KEY ("deleted_by_account_id") REFERENCES core.account("id") ON DELETE RESTRICT',
    ]
    table_sql = {
        name: template.replace("{org}", "organisation_id")
        .replace("{updated}", "updated_at_utc")
        .replace("{deleted}", "deleted_at_utc")
        for name, template in kinds["table"].items()
    }
    migration = [
        f'CREATE SCHEMA "{schema}";',
        f'SET search_path TO "{schema}", public;',
        f'CREATE TABLE "{schema}"."{table}" (\n' + ",\n".join(columns + constraints) + "\n);",
        table_sql["list_index"].format(table=table, schema=schema),
    ]
    for field in fields:
        kind = definitions[field["kind"]]
        column = _snake(field["column"])
        if kind.get("filter_index"):
            migration.append(
                table_sql["filter_index"].format(
                    table=table, schema=schema, column=column
                )
            )
        if kind.get("search_index"):
            migration.append(
                table_sql["search_index"].format(
                    table=table, schema=schema, column=column
                )
            )
        if kind.get("index"):
            migration.append(
                table_sql["index"].format(table=table, schema=schema, column=column)
            )
    for column in ("organisation_id", "created_by_account_id", "modified_by_account_id", "deleted_by_account_id"):
        migration.append(
            f'CREATE INDEX "idx_{table}_{column}" ON "{schema}"."{table}" ("{column}");'
        )
    migration.extend([
        table_sql["updated_at_trigger"].format(table=table),
        table_sql["soft_delete_trigger"].format(table=table),
        "RESET search_path;",
    ])
    source = """\"\"\"Create the {plural} table in its own schema.\"\"\"

from collections.abc import Sequence

from alembic import op

revision: str = {revision_literal}
down_revision: str | None = {down_revision_literal}
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        \"\"\"
{upgrade_sql}
        \"\"\"
    )


def downgrade() -> None:
    op.execute({drop_schema_literal})
""".format(plural=plural, revision=revision, down_revision=down_revision,
           revision_literal=_literal(revision),
           down_revision_literal=_literal(down_revision),
           drop_schema_literal=_literal(f'DROP SCHEMA "{schema}" CASCADE'),
           upgrade_sql="\n".join("        " + line for line in migration), schema=schema)
    return revision + ".py", source


def _permissions_source(one: str, plural: str) -> str:
    template = (STARTER_PYTHON / "apps/api/app/projects/permissions.py").read_text(
        encoding="utf-8"
    )
    template = template.replace('"projects"', "@@FEATURE_SLUG@@")
    return _remove_marks(_python_rename(template, one, plural)).replace(
        "@@FEATURE_SLUG@@", _literal(plural)
    )


def _routes_source(
    fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any]
) -> str:
    model = _pascal(one)
    module = _snake(plural)
    columns = [
        f"{module.upper()}_CSV_COLUMNS: tuple[",
        f"    CsvColumn[{model}],",
        "    ...,",
        "] = (",
    ]
    for field in fields:
        attr, kind = _field_attr(field), field["kind"]
        label = _words(field["name"])
        if kind == "date":
            value = [
                f"item.{attr}.isoformat()",
                f"if item.{attr} is not None",
                "else None",
            ]
        elif kind == "money":
            value = [
                f"item.{attr}_currency + ' ' + str(item.{attr})",
                f"if item.{attr} is not None",
                "else None",
            ]
        elif kind in ("number", "link"):
            value = [
                f"str(item.{attr})",
                f"if item.{attr} is not None",
                "else None",
            ]
        elif kind == "yes-no":
            value = [f'"Yes" if item.{attr} else "No"']
        else:
            value = [f"item.{attr}"]
        columns.extend(["    (", f"        {_literal(label)},"])
        if kind in ("date", "number", "link", "money"):
            columns.extend(
                [
                    "        lambda item: (",
                    *[f"            {line}" for line in value],
                    "        ),",
                ]
            )
        else:
            columns.append(f"        lambda item: {value[0]},")
        columns.append("    ),")
    columns.extend(
        [
            "    (",
            '        "Created (UTC)",',
            "        lambda item: utc_date_time(item.created_at_utc),",
            "    ),",
            "    (",
            '        "Updated (UTC)",',
            "        lambda item: utc_date_time(item.updated_at_utc),",
            "    ),",
            ")",
        ]
    )
    template = (STARTER_PYTHON / "apps/api/app/projects/routes.py").read_text(
        encoding="utf-8"
    )
    template = _python_rename(template, one, plural)
    template = template.replace(
        f'"/api/v1/{module}', f'"/api/v1/{plural}'
    )
    template = _replace_mark(template, "csv-fields", "\n".join(columns))
    return _remove_marks(template)


def _module_source(one: str, plural: str, *, include_mcp: bool) -> str:
    template = (STARTER_PYTHON / "apps/api/app/projects/__init__.py").read_text(
        encoding="utf-8"
    )
    template = _python_rename(template, one, plural)
    tools_import = (
        f"from app.{_snake(plural)}.tools import register_tools\nregister_tools()"
        if include_mcp
        else ""
    )
    template = _replace_mark(template, "tools", tools_import)
    return _remove_marks(template)


def _service_source(
    fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any], root: Path,
    *, include_mcp: bool,
) -> str:
    model, module = _pascal(one), _snake(plural)
    definitions = kinds["kinds"]
    name_field = next(field for field in fields if field["kind"] == "text" and not field.get("optional"))
    search_field = next(field for field in fields if field["kind"] in ("text", "email"))
    filter_fields = [field for field in fields if definitions[field["kind"]].get("filter_index")]
    sort_fields = [field for field in fields if field["kind"] != "long-text"]
    sort_fields += [
        {"name": "createdAtUtc", "column": "createdAtUtc", "kind": "datetime", "optional": False},
        {"name": "updatedAtUtc", "column": "updatedAtUtc", "kind": "datetime", "optional": False},
    ]
    sort_columns = {field["column"]: _field_attr(field) for field in sort_fields if field["name"] not in ("createdAtUtc", "updatedAtUtc")}
    sort_columns.update({"createdAtUtc": "created_at_utc", "updatedAtUtc": "updated_at_utc"})
    nullable = [field["column"] for field in sort_fields if field.get("optional") and field["kind"] != "yes-no"]
    sort_types = {}
    for field in sort_fields:
        kind = field["kind"]
        sort_types[field["column"]] = {
            "datetime": "datetime",
            "date": "date",
            "number": "decimal",
            "money": "decimal",
            "yes-no": "boolean",
            "link": "uuid",
        }.get(kind, "string")
    labels = {_field_attr(field): _words(field["name"]) for field in fields}
    labels_source = "{\n" + "\n".join(f"    {_literal(key)}: {_literal(value)}," for key, value in labels.items()) + "\n}"
    decimal_fields = tuple(
        _field_attr(field) for field in fields if field["kind"] in ("number", "money")
    )
    money_fields = tuple(_field_attr(field) for field in fields if field["kind"] == "money")
    inputs_create = []
    inputs_update = []
    for field in fields:
        attr, kind = _field_attr(field), field["kind"]
        value = f"input_data.{attr}"
        if kind in ("number", "money"):
            value = f"Decimal(input_data.{attr})"
            if field.get("optional"):
                value += f" if input_data.{attr} is not None else None"
        inputs_create.append(f"            {attr}={value},")
        inputs_update.append(f"        item.{attr} = {value}")
        if kind == "money":
            inputs_create.append(f"            {attr}_currency=DEFAULT_CURRENCY,")
    filter_lines = []
    for field in filter_fields:
        attr, kind = _field_attr(field), field["kind"]
        if kind == "yes-no":
            filter_lines.extend([
                f"    if query.{attr} is not None:",
                f"        filters.append(Model.{attr} == (query.{attr} == \"yes\"))",
            ])
        else:
            filter_lines.extend([
                f"    if query.{attr} is not None:",
                f"        filters.append(Model.{attr} == query.{attr})",
            ])
    search_clause = f"Model.{_field_attr(search_field)}.ilike(_search_pattern(query.search), escape=\"\\\\\")"
    sort_map = "\n".join(f"    {_literal(key)}: Model.{attr}," for key, attr in sort_columns.items())
    nullable_set = "(" + ", ".join(_literal(value) for value in nullable) + ("," if len(nullable) == 1 else "") + ")"
    link_imports = {}
    for field in fields:
        if field["kind"] == "link":
            link_imports[field["target"]] = _public_service(root, field["target"])
    links = []
    for target, service_name in link_imports.items():
        links.extend([f"from app.{_snake(target)} import {service_name}"])
    check_links = []
    for field in fields:
        if field["kind"] != "link":
            continue
        attr = _field_attr(field)
        service_name = link_imports[field["target"]]
        check_links.extend([
            f"        if input_data.{attr} is not None:",
            "            try:",
            f"                linked = {service_name}(self.db).get(account, input_data.{attr})",
            "            except ApiError as error:",
            "                if error.status_code != 404:",
            "                    raise",
            f"                self._link_not_found({_literal(field['column'])})",
            "            if linked.deleted_at_utc is not None:",
            f"                self._link_not_found({_literal(field['column'])})",
        ])
    link_body = "\n".join(check_links) if check_links else "        return None"
    data_fields = "\n".join(inputs_create)
    assigns = "\n".join(inputs_update)
    sort_attrs = "\n".join(f"    {_literal(key)}: {_literal(attr)}," for key, attr in sort_columns.items())
    cursor_parsers = []
    for kind, types in (
        ("datetime", [name for name, value in sort_types.items() if value == "datetime"]),
        ("date", [name for name, value in sort_types.items() if value == "date"]),
        ("decimal", [name for name, value in sort_types.items() if value == "decimal"]),
        ("integer", [name for name, value in sort_types.items() if value == "integer"]),
        ("boolean", [name for name, value in sort_types.items() if value == "boolean"]),
        ("uuid", [name for name, value in sort_types.items() if value == "uuid"]),
    ):
        if not types:
            continue
        type_names = "(" + ", ".join(_literal(value) for value in types) + ("," if len(types) == 1 else "") + ")"
        cursor_parsers.extend([f"            if sort_by in {type_names}:"])
        parser = {
            "datetime": "datetime.fromisoformat(text)",
            "date": "date.fromisoformat(text)",
            "decimal": "Decimal(text)",
            "integer": "int(text)",
            "boolean": 'text == "True"',
            "uuid": "UUID(text)",
        }[kind]
        if kind == "datetime":
            cursor_parsers.extend([
                "                value = datetime.fromisoformat(text)",
                "                if value.tzinfo is None:",
                "                    raise ValueError()",
                "                return value, UUID(cursor_id)",
            ])
        else:
            if kind == "boolean":
                cursor_parsers.extend([
                    '                if text not in ("True", "False"):',
                    "                    raise ValueError()",
                ])
            cursor_parsers.extend([f"                return {parser}, UUID(cursor_id)"])
    if [name for name, value in sort_types.items() if value == "string"]:
        names = [name for name, value in sort_types.items() if value == "string"]
        string_types = "(" + ", ".join(_literal(name) for name in names) + ("," if len(names) == 1 else "") + ")"
        cursor_parsers.extend([
            f"            if sort_by in {string_types}:",
            "                return text, UUID(cursor_id)",
        ])
    parsers = "\n".join(cursor_parsers)
    search_import = "date" if any(field["kind"] == "date" for field in fields) else None
    import_lines = [
        "import base64",
        "import binascii",
        "import json",
        "from collections.abc import Callable, Sequence" if include_mcp else "from collections.abc import Sequence",
        "from datetime import UTC, datetime" + (", date" if search_import else ""),
        "from decimal import Decimal, InvalidOperation" if "decimal" in sort_types.values() else "from decimal import Decimal",
        "from typing import Any, NoReturn",
        "from uuid import UUID, uuid7",
        "",
        "from sqlalchemy import and_, func, literal, or_, select",
        "from sqlalchemy.orm import Session as DbSession",
        "",
        "from app.auth import account_emails",
        "from app.core import AccountPrincipal, ApiError, has_permission"
        + (", DEFAULT_CURRENCY" if money_fields else ""),
        "from app.history import HistoryEntry, HistoryService, Subject",
        *links,
        f"from app.{module}.models import {model} as Model",
        f"from app.{module}.permissions import {_snake(one).upper()}_PERMISSIONS",
        f"from app.{module}.schema import (",
        f"    {model},",
        f"    {model}ExportQuery,",
        f"    {model}Input,",
        f"    {model}ListQuery,",
        f"    {model}ListResponse,",
        f"    {model}Paging,",
        ")",
        "",
    ]
    import_lines = [line for line in import_lines if line is not None]
    source = '''{imports}
# The changes route returns this many entries, newest first.
RECENT_CHANGES = 5
TOTAL_CAP = 10_000
SORT_COLUMNS: dict[str, Any] = {{
{sort_columns}
}}
SORT_ATTRIBUTES = {{
{sort_attributes}
}}
NULLABLE_SORT_FIELDS = {nullable}
FIELD_LABELS = {field_labels}
DECIMAL_FIELDS = {decimal_fields}
MONEY_FIELDS = {money_fields}
NAME_ATTRIBUTE = {name_attr}
STORED_FIELDS = tuple(
    name
    for name in {model}.model_fields
    if name not in {{"created_by_email", "modified_by_email", "deleted_by_email"}}
)


def _encode_cursor(sort_by: str, item: Model) -> str:
    value = getattr(item, SORT_ATTRIBUTES[sort_by])
    text = value.isoformat() if hasattr(value, "isoformat") else str(value)
    raw = json.dumps(
        [sort_by, text if value is not None else None, str(item.id)], ensure_ascii=False
    ).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _decode_cursor(sort_by: str, cursor: str, field: str) -> tuple[Any, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        cursor_sort, text, cursor_id = json.loads(raw)
        if (
            cursor_sort == sort_by
            and (text is None or isinstance(text, str))
            and isinstance(cursor_id, str)
        ):
            if text is None:
                if sort_by in NULLABLE_SORT_FIELDS:
                    return None, UUID(cursor_id)
                raise ValueError()
{cursor_parsers}
    except ({cursor_errors}):
        pass
    raise ApiError(
        400,
        "VALIDATION_ERROR",
        "Check the fields and try again.",
        {{
            "fieldErrors": [
                {{"field": field, "reason": "Open the first page of the list again."}}
            ]
        }},
    )


def _change_summary(item: Model, input_data: {model}Input) -> str:
    changes: list[str] = []
    for field, label in FIELD_LABELS.items():
        before, after = getattr(item, field), getattr(input_data, field)
        if field in DECIMAL_FIELDS and after is not None:
            after = Decimal(after)
        if before != after:
            if field in MONEY_FIELDS:
                currency = getattr(item, field + "_currency")
                before = f"{{currency}} {{before}}" if before is not None else before
                after = f"{{currency}} {{after}}" if after is not None else after
            changes.append(f"{{label}} changed from {{before}} to {{after}}")
    return "; ".join(changes)


def _search_pattern(term: str) -> str:
    escaped = term.replace("\\\\", "\\\\\\\\").replace("%", "\\\\%").replace("_", "\\\\_")
    return f"%{{escaped}}%"


def _sees_deleted(account: AccountPrincipal) -> bool:
    return has_permission(account.role, {permission}.restore)


def _filters(account: AccountPrincipal, query: {model}ExportQuery) -> list[Any]:
    filters: list[Any] = [Model.organisation_id == account.organisation_id]
    if not (query.deleted == "yes" and _sees_deleted(account)):
        filters.append(Model.deleted_at_utc.is_(None))
    if query.search:
        filters.append({search_clause})
{filter_body}
    return filters


class {model}Service:
    def __init__(
        self,
        db: DbSession,
        # forge:feature:mcp:start
        after_create: Callable[[DbSession, UUID], None] | None = None,
        # forge:feature:mcp:end
    ) -> None:
        self.db = db
        self.history = HistoryService(db)
        # forge:feature:mcp:start
        self.after_create = after_create
        # forge:feature:mcp:end

    def _responses(self, items: Sequence[Model]) -> list[{model}]:
        emails = account_emails(
            self.db,
            {{
                account_id
                for item in items
                for account_id in (
                    item.created_by_account_id,
                    item.modified_by_account_id,
                    item.deleted_by_account_id,
                )
                if account_id is not None
            }},
        )
        return [
            {model}.model_validate(
                {{
                    name: str(value)
                    if name in DECIMAL_FIELDS and value is not None
                    else value
                    for name in STORED_FIELDS
                    for value in (getattr(item, name),)
                }}
                | {{
                    "created_by_email": emails[item.created_by_account_id],
                    "modified_by_email": emails[item.modified_by_account_id],
                    "deleted_by_email": emails[item.deleted_by_account_id]
                    if item.deleted_by_account_id
                    else None,
                }}
            )
            for item in items
        ]

    def _response(self, item: Model) -> {model}:
        return self._responses([item])[0]

    def list(
        self, account: AccountPrincipal, query: {model}ListQuery
    ) -> {model}ListResponse:
        filters = _filters(account, query)
        column = SORT_COLUMNS[query.sort_by]
        backward = query.before is not None
        cursor = query.before if backward else query.after
        ascending = (query.sort_order == "asc") != backward
        statement = select(Model).where(*filters)
        if cursor is not None:
            value, cursor_id = _decode_cursor(
                query.sort_by, cursor, "before" if backward else "after"
            )
            if value is None:
                ties = and_(
                    column.is_(None),
                    Model.id > cursor_id if ascending else Model.id < cursor_id,
                )
                statement = statement.where(
                    or_(column.is_not(None), ties) if backward else ties
                )
            else:
                bound_value = literal(value, type_=column.type)
                beyond = column > bound_value if ascending else column < bound_value
                ties = and_(
                    column == value,
                    Model.id > cursor_id if ascending else Model.id < cursor_id,
                )
                choices = [beyond, ties]
                if not backward and query.sort_by in NULLABLE_SORT_FIELDS:
                    choices.append(column.is_(None))
                statement = statement.where(or_(*choices))
        order_column = column.asc() if ascending else column.desc()
        order_column = (
            order_column.nulls_first()
            if backward and query.sort_by in NULLABLE_SORT_FIELDS
            else order_column.nulls_last()
        )
        rows = list(
            self.db.scalars(
                statement.order_by(
                    order_column, Model.id.asc() if ascending else Model.id.desc()
                ).limit(query.limit + 1)
            ).all()
        )
        total = (
            self.db.scalar(
                select(func.count()).select_from(
                    select(Model.id).where(*filters).limit(TOTAL_CAP + 1).subquery()
                )
            )
            or 0
        )
        more = len(rows) > query.limit
        page = rows[: query.limit]
        if backward:
            page.reverse()
        has_next = bool(page) and (backward or more)
        has_previous = bool(page) and (more if backward else cursor is not None)
        return {model}ListResponse(
            items=self._responses(page),
            paging={model}Paging(
                limit=query.limit,
                next_cursor=_encode_cursor(query.sort_by, page[-1]) if has_next else None,
                previous_cursor=_encode_cursor(query.sort_by, page[0]) if has_previous else None,
                total=min(total, TOTAL_CAP),
                total_capped=total > TOTAL_CAP,
            ),
        )

    def list_all(
        self, account: AccountPrincipal, query: {model}ExportQuery
    ) -> Sequence[{model}]:
        items = self.db.scalars(
            select(Model)
            .where(*_filters(account, query))
            .order_by(Model.created_at_utc.desc(), Model.id.asc())
        ).all()
        return self._responses(items)

    def _find(self, account: AccountPrincipal, item_id: UUID, *conditions: Any) -> Model:
        item = self.db.scalar(
            select(Model).where(
                Model.id == item_id,
                Model.organisation_id == account.organisation_id,
                *conditions,
            )
        )
        if item is None:
            raise self._not_found()
        return item

    def _live(self, account: AccountPrincipal, item_id: UUID) -> Model:
        return self._find(account, item_id, Model.deleted_at_utc.is_(None))

    def _readable(self, account: AccountPrincipal, item_id: UUID) -> Model:
        if _sees_deleted(account):
            return self._find(account, item_id)
        return self._live(account, item_id)

    def get(self, account: AccountPrincipal, item_id: UUID) -> {model}:
        return self._response(self._readable(account, item_id))

    def changes(
        self, account: AccountPrincipal, item_id: UUID
    ) -> Sequence[HistoryEntry]:
        self._readable(account, item_id)
        return self.history.list_for_subject(account, item_id, RECENT_CHANGES)

    def _check_links(
        self,
        account: AccountPrincipal,
        input_data: {model}Input,
    ) -> None:
{link_body}

    @staticmethod
    def _link_not_found(field: str) -> NoReturn:
        raise ApiError(
            400,
            "VALIDATION_ERROR",
            "Check the fields and try again.",
            {{
                "fieldErrors": [
                    {{
                        "field": field,
                        "reason": "That linked item no longer exists. Choose another.",
                    }}
                ]
            }},
        )

    def create(self, account: AccountPrincipal, input_data: {model}Input) -> {model}:
        self._check_links(account, input_data)
        item = Model(
            id=uuid7(),
            organisation_id=account.organisation_id,
{create_fields}
            created_by_account_id=account.id,
            modified_by_account_id=account.id,
        )
        self.db.add(item)
        self.history.record(
            account,
            "{module}.created",
            "Created the {one}",
            Subject(item.id, getattr(item, NAME_ATTRIBUTE)),
        )
        # forge:feature:mcp:start
        if self.after_create is not None:
            self.after_create(self.db, item.id)
        # forge:feature:mcp:end
        self.db.commit()
        self.db.refresh(item)
        return self._response(item)

    def update(
        self, account: AccountPrincipal, item_id: UUID, input_data: {model}Input
    ) -> {model}:
        self._check_links(account, input_data)
        item = self._live(account, item_id)
        summary = _change_summary(item, input_data)
        # forge:feature:mcp:start
        if not summary:
            return self._response(item)
        # forge:feature:mcp:end
{update_fields}
        item.modified_by_account_id = account.id
        if summary:
            self.history.record(
                account,
                "{module}.changed",
                summary,
                Subject(item.id, getattr(item, NAME_ATTRIBUTE)),
            )
        self.db.commit()
        self.db.refresh(item)
        return self._response(item)

    def delete(self, account: AccountPrincipal, item_id: UUID) -> None:
        item = self._live(account, item_id)
        item.deleted_at_utc = datetime.now(UTC)
        item.deleted_by_account_id = account.id
        item.modified_by_account_id = account.id
        self.history.record(
            account,
            "{module}.deleted",
            "Deleted the {one}",
            Subject(item.id, getattr(item, NAME_ATTRIBUTE)),
        )
        self.db.commit()

    def restore(self, account: AccountPrincipal, item_id: UUID) -> {model}:
        item = self._find(account, item_id, Model.deleted_at_utc.is_not(None))
        item.deleted_at_utc = None
        item.deleted_by_account_id = None
        item.modified_by_account_id = account.id
        self.history.record(
            account,
            "{module}.restored",
            "Restored the {one}",
            Subject(item.id, getattr(item, NAME_ATTRIBUTE)),
        )
        self.db.commit()
        self.db.refresh(item)
        return self._response(item)

    @staticmethod
    def _not_found() -> ApiError:
        return ApiError(404, "{error_code}_NOT_FOUND", "The {one} was not found.")
'''
    rendered = source.format(
        imports="\n".join(import_lines), sort_columns=sort_map,
        sort_attributes=sort_attrs, nullable=nullable_set,
        field_labels=labels_source, name_attr=_literal(_field_attr(name_field)),
        cursor_parsers=parsers, model=model,
        cursor_errors="binascii.Error, ValueError, TypeError" + (
            ", InvalidOperation" if "decimal" in sort_types.values() else ""
        ),
        search_clause=search_clause, filter_body="\n".join(filter_lines),
        link_body=link_body, create_fields=data_fields, update_fields=assigns,
        decimal_fields=_literal(decimal_fields), money_fields=_literal(money_fields),
        module=module, one=one.replace("-", " "), permission=_snake(one).upper() + "_PERMISSIONS",
        error_code=_snake(one).upper(),
    )
    return _feature_mcp(rendered, include_mcp)


def render_feature_python(
    fields: list[dict[str, Any]],
    one: str,
    plural: str,
    kinds: dict[str, Any],
    root: Path,
    *, include_mcp: bool = True,
) -> dict[str, str]:
    from forge.feature_python_contracts import _schema_source, render_python_contracts
    from forge.feature_python_tests import render_python_tests
    from forge.feature_python_tools import render_feature_tools

    module = _snake(plural)
    migration_name, migration = _migration_source(fields, one, plural, kinds, root)
    api = f"apps/api/app/{module}"
    files = {
        f"{api}/__init__.py": _module_source(one, plural, include_mcp=include_mcp),
        f"{api}/models.py": _model_source(fields, one, plural, kinds),
        f"{api}/schema.py": _schema_source(fields, one, plural, kinds),
        f"{api}/service.py": _service_source(fields, one, plural, kinds, root, include_mcp=include_mcp),
        f"{api}/routes.py": _routes_source(fields, one, plural, kinds),
        f"{api}/permissions.py": _permissions_source(one, plural),
        f"apps/api/migrations/versions/{migration_name}": migration,
        f"apps/api/tests/test_{module}.py": render_python_tests(
            fields, one, plural, kinds, root, include_mcp=include_mcp
        ),
        f"libs/{plural}/contracts/src/index.ts": render_python_contracts(
            fields, one, plural, kinds
        ),
    }
    if include_mcp:
        files[f"{api}/tools.py"] = render_feature_tools(fields, one, plural, kinds, root)
    return files
