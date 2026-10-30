"""Render a feature's contracts and API from the starter's marked projects files."""
from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

STARTER = Path(__file__).parent / "templates/starter"
MARKER = re.compile(r"(?P<indent>^[ \t]*)// forge:feature:(?P<name>[\w-]+):start\n.*?^[ \t]*// forge:feature:(?P=name):end\n?", re.M | re.S)


def _replace(text: str, name: str, body: str) -> str:
    matches = list(MARKER.finditer(text))
    matches = [match for match in matches if match.group("name") == name]
    if len(matches) != 1:
        raise ValueError(f"The projects starter needs one {name} feature marker.")
    match = matches[0]
    indent = match.group("indent")
    body = "\n".join(indent + line if line else "" for line in body.rstrip().splitlines())
    return text[:match.start()] + body + "\n" + text[match.end():]


def _feature_mcp(text: str, include: bool) -> str:
    """Keep tools and retry keys only when the app has their shared core helpers."""
    matches = [match for match in MARKER.finditer(text) if match.group("name") in {"mcp", "mcp-cases", "retry-key"}]
    for match in reversed(matches):
        if include:
            lines = match.group(0).splitlines(keepends=True)
            replacement = "".join(lines[1:-1])
        else:
            replacement = ""
        text = text[:match.start()] + replacement + text[match.end():]
    return text


def _tool_fields(fields: list[dict[str, Any]], kinds: dict[str, Any]) -> tuple[str, str]:
    concise = [_column(field) for field in fields if kinds["kinds"][field["kind"]]["column"]]
    links = [field for field in fields if field["kind"] == "link"]
    imports = sorted({
        f"import {{ {field['target'].replace('-', '_').upper()}_API }} from '@app/{field['target']}-contracts';"
        for field in links
    })
    mapping = "\n".join(
        f"  {_column(field)}: {field['target'].replace('-', '_').upper()}_API,"
        for field in links
    )
    link_body = f"\n{mapping}\n" if mapping else ""
    label = _column(next(field for field in fields if field["kind"] == "text" and not field.get("optional")))
    body = f"label: {_literal(label)},\nconcise: [{', '.join(_literal(name) for name in concise)}],\nlinks: {{{link_body}}},"
    return body, "\n".join(imports)


def _pascal(value: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in value.split("-"))


def _camel(value: str) -> str:
    name = _pascal(value)
    return name[:1].lower() + name[1:]


def _label(value: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value).replace("-", " ").title()


def _column(field: dict[str, Any]) -> str:
    return field.get("column", field["name"] + "Id" if field["kind"] == "link" else field["name"])


def _status_name(one: str, field: dict[str, Any]) -> str:
    return _camel(one) + _pascal(_column(field)) + "Schema"


def _status_type(one: str, field: dict[str, Any]) -> str:
    return _pascal(one) + _pascal(_column(field))


def _status_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [field for field in fields if field["kind"] == "status"]


def _literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _sample(field: dict[str, Any], kinds: dict[str, Any], changed: bool = False) -> Any:
    definition = kinds["kinds"][field["kind"]]
    value = definition["changed" if changed else "sample"]
    if field["kind"] == "status":
        options = field["options"]
        candidate = value if value in options else None
        if changed and len(options) > 1:
            candidate = next((option for option in options if option != definition["sample"]), options[0])
        return candidate or options[0]
    if field["kind"] in ("number", "money"):
        return str(value)
    return value


def _input_expr(field: dict[str, Any], one: str, kinds: dict[str, Any]) -> str:
    kind = field["kind"]
    if kind == "status":
        expr = _status_name(one, field)
    elif kind == "text":
        expr = "z.string().trim().min(1).max(200)"
    elif kind == "long-text":
        expr = "z.string().max(10000)"
    elif kind in ("number", "money"):
        expr = kinds["kinds"][kind]["zod"]
    elif kind == "date":
        expr = "z.string().regex(/^\\d{4}-\\d{2}-\\d{2}$/).refine((value) => { const date = new Date(`${value}T00:00:00.000Z`); return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value; }, 'Enter a real date as YYYY-MM-DD.')"
    elif kind == "yes-no":
        expr = "z.boolean()"
    elif kind == "email":
        expr = "z.string().trim().email().max(254)"
    elif kind == "link":
        expr = "z.string().uuid()"
    else:
        raise ValueError(f"Unknown field kind: {kind}")
    if field.get("optional"):
        expr += ".optional()"
    label = _label(field["name"])
    description = f"The linked item from {field['target']}." if kind == "link" else f"The {label.lower()}."
    return f"{expr}.meta({{ description: {_literal(description)}, example: {_literal(_sample(field, kinds))} }})"


def _response_type(field: dict[str, Any], one: str) -> str:
    kind = field["kind"]
    base = "string" if kind in ("text", "long-text", "email", "date", "link", "number", "money") else "boolean" if kind == "yes-no" else _status_type(one, field)
    return base + (" | null" if field.get("optional") and kind != "yes-no" else "")


def _response_value(field: dict[str, Any], one: str) -> str:
    name = _column(field)
    kind = field["kind"]
    value = f"featureItem.{name}"
    if kind == "status":
        parsed = f"{_status_name(one, field)}.parse({value})"
        return f"{value} === null ? null : {parsed}" if field.get("optional") else parsed
    if kind == "date":
        formatted = f"{value}.toISOString().slice(0, 10)"
        return f"{value}?.toISOString().slice(0, 10) ?? null" if field.get("optional") else formatted
    if kind in ("number", "money"):
        return f"{value} === null ? null : {value}.toString()" if field.get("optional") else f"{value}.toString()"
    return value


def _data_value(field: dict[str, Any]) -> str:
    name, kind = _column(field), field["kind"]
    value = f"input.{name}"
    if kind == "date":
        return f"{value} ? new Date({value}) : null" if field.get("optional") else f"new Date({value})"
    if kind == "yes-no":
        return f"{value} ?? false" if field.get("optional") else value
    if kind in ("number", "money"):
        return f"{value} === undefined ? null : new Prisma.Decimal({value})" if field.get("optional") else f"new Prisma.Decimal({value})"
    if field.get("optional"):
        return f"{value} ?? null"
    return value


def _cursor_blocks(fields: list[dict[str, Any]], one: str) -> tuple[str, str]:
    model = _pascal(one)
    optional = [field for field in fields if field.get("optional") and field["kind"] != "yes-no"]
    nullable = [f"'{_column(field)}'" for field in optional]
    date_fields = [f"'{_column(field)}'" for field in fields if field["kind"] == "date"]
    date_fields += ["'createdAtUtc'", "'updatedAtUtc'"]
    number_fields = [f"'{_column(field)}'" for field in fields if field["kind"] == "number"]
    money_fields = [f"'{_column(field)}'" for field in fields if field["kind"] == "money"]
    bool_fields = [f"'{_column(field)}'" for field in fields if field["kind"] == "yes-no"]
    uuid_fields = [f"'{_column(field)}'" for field in fields if field["kind"] == "link"]
    cases = []
    for names, parser in (
        (date_fields, "if (typeof value === 'string' && !Number.isNaN(new Date(value).getTime())) return { value: new Date(value), id }"),
        (number_fields, "if (typeof value === 'string' && /^-?\\d{1,15}(?:\\.\\d{1,4})?$/.test(value)) return { value: new Prisma.Decimal(value), id }"),
        (money_fields, "if (typeof value === 'string' && /^-?\\d{1,15}(?:\\.\\d{1,4})?$/.test(value)) return { value: new Prisma.Decimal(value), id }"),
        (bool_fields, "if (typeof value === 'boolean') return { value, id }"),
        (uuid_fields, "if (typeof value === 'string' && UUID.test(value)) return { value, id }"),
    ):
        if names:
            cases.extend(f"    case {name}:" for name in names)
            cases.extend([f"      {parser};", "      break;"])
    non_strings = set(number_fields + money_fields + bool_fields + date_fields + uuid_fields)
    string_fields = [f"'{_column(field)}'" for field in fields if f"'{_column(field)}'" not in non_strings]
    if string_fields:
        cases.extend(f"    case {name}:" for name in string_fields)
        cases.extend(["      if (typeof value === 'string') return { value, id };", "      break;"])
    decode = f"""const NULLABLE_SORT_FIELDS = new Set<SortBy>([{', '.join(nullable)}]);
const BOOLEAN_SORT_FIELDS = new Set<SortBy>([{', '.join(bool_fields)}]);
function decodeCursor(sortBy: SortBy, cursor: string, backward: boolean): {{ value: string | number | boolean | Date | Prisma.Decimal | null; id: string }} {{
  try {{
    const [cursorSort, value, id] = JSON.parse(Buffer.from(cursor, 'base64url').toString('utf8')) as unknown[];
    if (cursorSort === sortBy && typeof id === 'string' && UUID.test(id)) {{
      if (value === null && NULLABLE_SORT_FIELDS.has(sortBy)) return {{ value, id }};
      switch (sortBy) {{
{chr(10).join(cases)}
      }}
    }}
  }} catch {{
    // An unreadable cursor gets the same field error as one for another sort.
  }}
  throw new BadRequestException({{
    code: 'VALIDATION_ERROR',
    message: 'Check the fields and try again.',
    details: {{ fieldErrors: [{{ field: backward ? 'before' : 'after', reason: 'Open the first page of the list again.' }}] }},
  }});
}}"""
    after = f"""function sortOrderBy(sortBy: SortBy, order: 'asc' | 'desc', backward: boolean): Prisma.{model}OrderByWithRelationInput {{
  return NULLABLE_SORT_FIELDS.has(sortBy)
    ? {{ [sortBy]: {{ sort: order, nulls: backward ? 'first' : 'last' }} }} as Prisma.{model}OrderByWithRelationInput
    : {{ [sortBy]: order }} as Prisma.{model}OrderByWithRelationInput;
}}

function afterCursor(sortBy: SortBy, order: 'asc' | 'desc', cursor: {{ value: string | number | boolean | Date | Prisma.Decimal | null; id: string }}, backward: boolean): Prisma.{model}WhereInput {{
  const beyond = order === 'asc' ? 'gt' : 'lt';
  if (cursor.value === null) {{
    const choices: Prisma.{model}WhereInput[] = [{{ [sortBy]: null, id: {{ [beyond]: cursor.id }} }} as Prisma.{model}WhereInput];
    if (backward) choices.push({{ [sortBy]: {{ not: null }} }} as Prisma.{model}WhereInput);
    return {{ OR: choices }};
  }}
  const choices: Prisma.{model}WhereInput[] = [
    {{ [sortBy]: cursor.value, id: {{ [beyond]: cursor.id }} }} as Prisma.{model}WhereInput,
  ];
  if (BOOLEAN_SORT_FIELDS.has(sortBy) && typeof cursor.value === 'boolean') {{
    if ((order === 'asc' && cursor.value === false) || (order === 'desc' && cursor.value === true)) {{
      choices.unshift({{ [sortBy]: !cursor.value }} as Prisma.{model}WhereInput);
    }}
  }} else {{
    choices.unshift({{ [sortBy]: {{ [beyond]: cursor.value }} }} as Prisma.{model}WhereInput);
  }}
  if (!backward && NULLABLE_SORT_FIELDS.has(sortBy)) choices.push({{ [sortBy]: null }} as Prisma.{model}WhereInput);
  return {{ OR: choices }};
}}"""
    return decode, after


def _filters(fields: list[dict[str, Any]], one: str, kinds: dict[str, Any]) -> str:
    search = next(field for field in fields if field["kind"] in ("text", "email"))
    lines = [f"  search: z.string().trim().max(200).optional().meta({{ description: 'Text to find in the {_label(search['name']).lower()}, up to 200 characters.', example: 'example' }}),"]
    for field in fields:
        column, kind = _column(field), field["kind"]
        if kind == "status":
            expr = f"{_status_name(one, field)}.optional()"
        elif kind == "link":
            expr = "z.string().uuid().optional()"
        elif kind == "yes-no":
            expr = "z.enum(['yes', 'no']).optional()"
        else:
            continue
        example = 'yes' if kind == 'yes-no' else _sample(field, kinds)
        lines.append(f"  {column}: {expr}.meta({{ description: 'Filter by {_label(field['name']).lower()}.', example: {_literal(example)} }}),")
    lines.append("  deleted: z.enum(['yes']).optional().meta({ description: 'Show deleted items too; only a caller with the restore permission gets them.', example: 'yes' }),")
    return f"const {_camel(one)}Filters = {{\n" + "\n".join(lines) + "\n};"


def _field_filter_where(fields: list[dict[str, Any]]) -> str:
    search = next(field for field in fields if field["kind"] in ("text", "email"))
    clauses = [f"...(filters.search ? {{ {_column(search)}: {{ contains: filters.search.replace(/[\\\\%_]/g, '\\\\$&'), mode: 'insensitive' as const }} }} : {{}}),"]
    for field in fields:
        column, kind = _column(field), field["kind"]
        if kind == "status":
            clauses.append(f"...(filters.{column} ? {{ {column}: filters.{column} }} : {{}}),")
        elif kind == "link":
            clauses.append(f"...(filters.{column} ? {{ {column}: filters.{column} }} : {{}}),")
        elif kind == "yes-no":
            clauses.append(f"...(filters.{column} ? {{ {column}: filters.{column} === 'yes' }} : {{}}),")
    return "\n".join(clauses)


def _field_labels(fields: list[dict[str, Any]]) -> str:
    labels = ", ".join(f"{_column(field)}: {_literal(_label(field['name']))}" for field in fields)
    return f"const FIELD_LABELS: Record<keyof FeatureInput, string> = {{ {labels} }};"


def _change_summary(fields: list[dict[str, Any]]) -> str:
    links = ", ".join(_literal(_column(field)) for field in fields if field["kind"] == "link")
    number_fields = ", ".join(_literal(_column(field)) for field in fields if field["kind"] == "number")
    money_fields = ", ".join(_literal(_column(field)) for field in fields if field["kind"] == "money")
    date_fields = ", ".join(_literal(_column(field)) for field in fields if field["kind"] == "date")
    boolean_fields = ", ".join(_literal(_column(field)) for field in fields if field["kind"] == "yes-no")
    optional_booleans = ", ".join(_literal(_column(field)) for field in fields if field["kind"] == "yes-no" and field.get("optional"))
    display_formats = []
    if money_fields:
        display_formats.append("if (MONEY_FIELDS.has(field)) return formatMoney(String(value), record[`${field}Currency` as keyof FeatureRecord] as string);")
    if number_fields:
        display_formats.append("if (NUMBER_FIELDS.has(field)) return formatNumber(Number(value), 4);")
    if date_fields:
        display_formats.append("if (DATE_FIELDS.has(field)) return formatDate(value instanceof Date ? value : String(value), 'UTC');")
    if boolean_fields:
        display_formats.append("if (BOOLEAN_FIELDS.has(field)) return value ? 'Yes' : 'No';")
    formatted_values = "\n  ".join(display_formats)
    money_set = f"const MONEY_FIELDS = new Set<keyof FeatureInput>([{money_fields}]);" if money_fields else ""
    date_set = f"const DATE_FIELDS = new Set<keyof FeatureInput>([{date_fields}]);" if date_fields else ""
    boolean_set = f"const BOOLEAN_FIELDS = new Set<keyof FeatureInput>([{boolean_fields}]);" if boolean_fields else ""
    record_parameter = ", record: FeatureRecord" if money_fields else ""
    record_argument = ", before" if money_fields else ""
    return f"""const LINK_FIELDS = new Set<keyof FeatureInput>([{links}]);
const NUMBER_FIELDS = new Set<keyof FeatureInput>([{number_fields}]);
{money_set}
{date_set}
{boolean_set}
const OPTIONAL_BOOLEAN_FIELDS = new Set<keyof FeatureInput>([{optional_booleans}]);

function changeValue(field: keyof FeatureInput, value: unknown): string | null {{
  if (value === undefined && OPTIONAL_BOOLEAN_FIELDS.has(field)) value = false;
  if (value === null || value === undefined) return null;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (NUMBER_FIELDS.has(field){' || MONEY_FIELDS.has(field)' if money_fields else ''}) return new Prisma.Decimal(String(value)).toString();
  return String(value);
}}

function displayValue(field: keyof FeatureInput, value: unknown{record_parameter}): string {{
  if (value === undefined && OPTIONAL_BOOLEAN_FIELDS.has(field)) value = false;
  if (value === null || value === undefined) return 'None';
  if (LINK_FIELDS.has(field)) return 'a linked item';
  {formatted_values}
  return changeValue(field, value) ?? 'None';
}}

function changeSummary(before: FeatureRecord, input: FeatureInput): string {{
  return (Object.keys(FIELD_LABELS) as (keyof FeatureInput)[])
    .filter((field) => changeValue(field, before[field]) !== changeValue(field, input[field]))
    .map((field) => LINK_FIELDS.has(field)
      ? `${{FIELD_LABELS[field]}} changed`
      : `${{FIELD_LABELS[field]}} changed from ${{displayValue(field, before[field]{record_argument})}} to ${{displayValue(field, input[field]{record_argument})}}`)
    .join('; ');
}}"""


def _link_code(fields: list[dict[str, Any]]) -> tuple[str, str, str, str]:
    links = [field for field in fields if field["kind"] == "link"]
    imports = []
    injections = []
    checks = []
    for index, target in enumerate(sorted({field["target"] for field in links})):
        title = _pascal(target)
        imports.append(f"import {{ {target.replace('-', '_').upper()}_API, type {title}Api as LinkedModule{index} }} from '@app/{target}-contracts';")
        injections.extend([
            f"@Inject({target.replace('-', '_').upper()}_API) private readonly {_camel(target)}Api: LinkedModule{index},"
        ])
    for field in links:
        column, target = _column(field), field["target"]
        label = _label(field["name"]).lower()
        checks.append(f"""    if (input.{column} !== undefined && input.{column} !== null) {{
      try {{
        const linked = await this.{_camel(target)}Api.get(account, input.{column});
        if (linked.deletedAtUtc !== null) throw this.invalidLink({_literal(column)}, {_literal(label)});
      }} catch (error) {{
        if (error instanceof NotFoundException) throw this.invalidLink({_literal(column)}, {_literal(label)});
        throw error;
      }}
    }}""")
    if not links:
        return "", "", "", ""
    validation = f"""private async validateLinks(account: AccountPrincipal, input: FeatureInput): Promise<void> {{
{chr(10).join(checks)}
  }}

  private invalidLink(field: string, target: string): BadRequestException {{
    return new BadRequestException({{
      code: 'VALIDATION_ERROR',
      message: 'Check the fields and try again.',
      details: {{ fieldErrors: [{{ field, reason: `That ${{target}} no longer exists. Choose another.` }}] }},
    }});
  }}"""
    return "\n".join(imports), "\n    ".join(injections), validation, "await this.validateLinks(account, input);"


def _dto_fields(fields: list[dict[str, Any]], one: str, kinds: dict[str, Any]) -> str:
    output = []
    for field in fields:
        kind, column = field["kind"], _column(field)
        label, sample = _label(field["name"]), _sample(field, kinds)
        base = "Boolean" if kind == "yes-no" else "String"
        extra = f", enum: {json.dumps(field['options'])}" if kind == "status" else ""
        nullable = field.get("optional") and kind != "yes-no"
        if nullable:
            extra += ", nullable: true"
        output.extend([
            f"  @ApiProperty({{ description: {_literal('The ' + label.lower() + '.')}, type: {base}{extra}, example: {_literal(sample)} }})",
            f"  {column}!: {(' | '.join(_literal(option) for option in field['options']) if kind == 'status' else _response_type(field, one))}{' | null' if nullable and kind == 'status' else ''};",
        ])
        if kind == "money":
            output.extend([
                "  @ApiProperty({ description: 'The stored currency code.', type: String, example: 'INR' })",
                f"  {column}Currency!: string;",
            ])
    return "\n".join(output)


def _csv_fields(fields: list[dict[str, Any]], kinds: dict[str, Any]) -> str:
    variable = "featureItem"
    output = []
    for field in fields:
        column, kind = _column(field), field["kind"]
        value = f"{variable}.{column}"
        if kind == "money":
            formatted = kinds["kinds"][kind]["csv"].replace("{name}", column).replace("row.", variable + ".")
            value = f"{value} === null ? '' : {formatted}"
        elif kind == "number":
            value = f"{value} === null ? '' : formatNumber(Number({value}), 4)"
        elif kind == "date":
            value = f"{value} === null ? '' : formatDate({value}, 'UTC')"
        elif kind == "yes-no":
            value = f"{value} ? 'Yes' : 'No'"
        elif field.get("optional"):
            value = f"{value} ?? ''"
        output.append(f"  {{ header: {_literal(_label(field['name']))}, value: ({variable}) => {value} }},")
    return "\n".join(output)


def _format_imports(fields: list[dict[str, Any]], *, include_datetime: bool = False) -> str:
    names = {"formatDateTime"} if include_datetime else set()
    for field in fields:
        if field["kind"] == "date":
            names.add("formatDate")
        elif field["kind"] == "number":
            names.add("formatNumber")
        elif field["kind"] == "money":
            names.add("formatMoney")
            if not include_datetime:
                names.add("DEFAULT_CURRENCY")
    return ", ".join(sorted(names))



def _renamed_source(text: str, one: str, plural: str) -> str:
    singular_var, plural_var = _camel(one), _camel(plural)
    singular_model, plural_model = _pascal(one), _pascal(plural)
    names = {
        "projects": plural_var, "Projects": plural_model, "PROJECTS": plural.replace("-", "_").upper(),
        "project": singular_var, "Project": singular_model, "PROJECT": one.replace("-", "_").upper(),
    }
    renamed = re.sub(r"projects|Projects|PROJECTS|project|Project|PROJECT", lambda match: names[match[0]], text)
    # Identifiers use camelCase; only source literals that form paths or fixed copy use slugs/words.
    renamed = renamed.replace(f"@app/{plural_var}-", f"@app/{plural}-")
    renamed = renamed.replace(f"./{plural_var}.", f"./{plural}.")
    renamed = renamed.replace(f"'/api/v1/{plural_var}", f"'/api/v1/{plural}")
    renamed = renamed.replace(f'"/api/v1/{plural_var}', f'"/api/v1/{plural}')
    renamed = renamed.replace(f"'{plural_var}'", f"'{plural}'")
    renamed = renamed.replace(f"'{plural_var}_create'", f"'{plural.replace('-', '_')}_create'")
    renamed = renamed.replace(f"'{plural_var}.csv'", f"'{plural}.csv'")
    renamed = renamed.replace(f"'{singular_var}.created'", f"'{one}.created'")
    renamed = renamed.replace(f"'{singular_var}.changed'", f"'{one}.changed'")
    renamed = renamed.replace(f"'{singular_var}.deleted'", f"'{one}.deleted'")
    renamed = renamed.replace(f"'{singular_var}.restored'", f"'{one}.restored'")
    singular_words, plural_words = _label(one).lower(), _label(plural).lower()
    renamed = renamed.replace(f"'{plural_model}'", f"'{_label(plural)}'")
    for verb in ("Created", "Deleted", "Restored"):
        renamed = renamed.replace(f"'{verb} the {singular_var}'", f"'{verb} the {singular_words}'")
    renamed = renamed.replace(f"'The {singular_var} was not found.'", f"'The {singular_words} was not found.'")
    renamed = renamed.replace(f"'The {singular_var} identifier.'", f"'The {singular_words} identifier.'")
    renamed = renamed.replace(f"'Create a {singular_var} in your organisation.'", f"'Create a {singular_words} in your organisation.'")
    renamed = renamed.replace(f"'Read one {singular_var} in your organisation.'", f"'Read one {singular_words} in your organisation.'")
    renamed = renamed.replace(f"'Replace a {singular_var} in your organisation.'", f"'Replace a {singular_words} in your organisation.'")
    renamed = renamed.replace(f"'Soft-delete a {singular_var} in your organisation.'", f"'Soft-delete a {singular_words} in your organisation.'")
    renamed = renamed.replace(f"'List the newest 5 changes to one {singular_var} in your organisation, newest first.'",
                              f"'List the newest 5 changes to one {singular_words} in your organisation, newest first.'")
    renamed = renamed.replace(f"'List your organisation’s {plural_var}.'", f"'List your organisation’s {plural_words}.'")
    renamed = renamed.replace(f"'Download the {plural_var} that match", f"'Download the {plural_words} that match")
    renamed = renamed.replace(f"'The {plural_var}.csv file:", f"'The {plural}.csv file:")
    return renamed


def render_feature_api(
    fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any], *, include_mcp: bool = True
) -> dict[str, str]:
    """Return the renamed contracts/server sources and generated API tests."""
    model, title = _pascal(one), _pascal(plural)
    statuses = _status_fields(fields)
    # The approved list table omits long-text columns.
    sort_fields = [field for field in fields if field["kind"] != "long-text"]
    link_imports, injections, link_validation, link_call = _link_code(fields)
    decode, after = _cursor_blocks(sort_fields, one)
    name_field = next(field for field in fields if field["kind"] == "text" and not field.get("optional"))
    filter_where = _field_filter_where(fields)
    from forge.feature_tests import render_api_tests, render_mcp_cases

    contract_imports = ", ".join([
        *(_status_name(one, field) for field in statuses),
        f"type {model} as FeatureResponse", f"type {model}ExportQuery as FeatureExportQuery",
        f"type {model}Input as FeatureInput", f"type {model}ListQuery as FeatureListQuery",
        f"type {title}Api as FeaturePublicApi",
    ])
    csv_fields = ", ".join(_label(field["name"]) for field in fields)
    service_format_imports = _format_imports(fields)
    controller_format_imports = _format_imports(fields, include_datetime=True)

    sources = {
        "libs/projects/contracts/src/index.ts": [
            ("status-schema", "\n".join(f"export const {_status_name(one, field)} = z.enum({json.dumps(field['options'])});" for field in statuses)),
            ("schema-fields", "\n".join(f"  {_column(field)}: {_input_expr(field, one, kinds)}," for field in fields)),
            ("filters", _filters(fields, one, kinds)),
            ("sort-fields", ", ".join(_literal(_column(field)) for field in sort_fields) + ","),
            ("status-type", "\n".join(f"export type {_status_type(one, field)} = z.infer<typeof {_status_name(one, field)}>;" for field in statuses)),
            ("response-fields", "\n".join(f"  {_column(field)}: {_response_type(field, one)};" +
                (f"\n  {_column(field)}Currency: string;" if field["kind"] == "money" else "") for field in fields)),
        ],
        "libs/projects/server/src/projects.service.ts": [
            ("link-imports", link_imports), ("field-labels", _field_labels(fields)),
            ("change-summary", _change_summary(fields)),
            ("response-fields", "\n    ".join(f"{_column(field)}: {_response_value(field, one)}," +
                (f"\n    {_column(field)}Currency: featureItem.{_column(field)}Currency," if field["kind"] == "money" else "") for field in fields)),
            ("cursor-decode", decode), ("cursor-after", after),
            ("field-filters", filter_where),
            ("link-injections", injections), ("link-validation", link_validation),
            ("link-validation-create", link_call), ("link-validation-update", link_call),
            ("create-fields", "\n          ".join(f"{_column(field)}: {_data_value(field)}," +
                (f"\n          {_column(field)}Currency: DEFAULT_CURRENCY," if field["kind"] == "money" else "") for field in fields)),
            ("update-fields", "\n          ".join(f"{_column(field)}: {_data_value(field)}," for field in fields)),
            ("history-created-name", f"name: featureItem.{_column(name_field)},"),
            ("history-changed-name", f"name: featureItem.{_column(name_field)},"),
            ("history-deleted-name", f"name: featureItem.{_column(name_field)},"),
            ("history-restored-name", f"name: featureItem.{_column(name_field)},"),
            ("delete-name", f"{_column(name_field)}: true,"),
        ],
        "libs/projects/server/src/projects.dto.ts": [("dto-fields", _dto_fields(fields, one, kinds))],
        "libs/projects/server/src/projects.controller.ts": [
            ("csv-fields", _csv_fields(fields, kinds)),
            ("csv-description", f"@ApiResponse({{ status: 200, description: {_literal(f'The {plural}.csv file: {csv_fields}, Created (UTC) and Updated (UTC).')} }})"),
        ],
        "apps/api/test/projects.e2e-spec.ts": [
            ("generated-tests", render_api_tests(fields, one, plural, kinds))
        ],
    }
    if include_mcp:
        sources["apps/api/test/projects.e2e-spec.ts"].append(
            ("mcp-cases", render_mcp_cases(fields, one, plural, kinds))
        )
    for source_path in (
        "libs/projects/server/src/projects.module.ts",
        "libs/projects/server/src/projects.permissions.ts",
        "libs/projects/server/src/index.ts",
    ):
        sources[source_path] = []
    if include_mcp:
        tool_fields, link_imports = _tool_fields(fields, kinds)
        sources["libs/projects/server/src/projects.tools.ts"] = [
            ("link-imports", link_imports),
            ("tool-fields", tool_fields),
        ]
    result: dict[str, str] = {}
    for source_path, replacements in sources.items():
        source = (STARTER / source_path).read_text(encoding="utf-8")
        if source_path.endswith(("projects.service.ts", "projects.controller.ts")):
            # Keep template locals and imported type aliases independent of feature names:
            # e.g. "responses" must not redeclare the response helper's local variable.
            source = source.replace("import type { Prisma, Project as ProjectRecord } from '@prisma/client';", "__FEATURE_RECORD_IMPORT__")
            aliases = {"Project": "FeatureResponse", "ProjectRecord": "FeatureRecord",
                       "ProjectInput": "FeatureInput", "ProjectListQuery": "FeatureListQuery",
                       "ProjectExportQuery": "FeatureExportQuery", "ProjectsApi": "FeaturePublicApi",
                       "PrismaService": "FeatureDatabase"}
            source = re.sub(r"\b(?:" + "|".join(aliases) + r")\b", lambda match: aliases[match[0]], source)
            source = source.replace("import { FeatureDatabase } from '@app/core-server';", "import { PrismaService as FeatureDatabase } from '@app/core-server';")
            source = source.replace("this.projects", "this.__featureItems")
            source = re.sub(r"\bconst (project|projects)\b", lambda match: "const __featureItem" + ("s" if match[1] == "projects" else ""), source)
            source = re.sub(r'''(?<![.'"/\w])\b(project|projects)\b(?=[:.,)\[\];])''',
                            lambda match: "__featureItem" + ("s" if match[1] == "projects" else ""), source)
        source = _renamed_source(source, one, plural)
        source = source.replace("__featureItems", "featureItems").replace("__featureItem", "featureItem")
        for marker, body in replacements:
            source = _replace(source, marker, body)
        source = _feature_mcp(source, include_mcp)
        if source_path.endswith("projects.service.ts"):
            source = re.sub(r"import \{[^}]+\} from '@app/" + re.escape(plural) + r"-contracts';",
                            f"import {{ {contract_imports} }} from '@app/{plural}-contracts';", source, count=1)
            source = source.replace("__FEATURE_RECORD_IMPORT__",
                                    f"import {{ Prisma }} from '@prisma/client';\nimport type {{ {model} as FeatureRecord }} from '@prisma/client';")
            if service_format_imports:
                source = source.replace(
                    "import { HISTORY_API, type HistoryApi } from '@app/history-contracts';",
                    "import { HISTORY_API, type HistoryApi } from '@app/history-contracts';\n"
                    f"import {{ {service_format_imports} }} from '@app/shared-util';",
                )
            source = source.replace("orderBy: [{ [query.sortBy]: order }, { id: order }],",
                                    "orderBy: [sortOrderBy(query.sortBy, order, backward), { id: order }],")
            source = source.replace("afterCursor(query.sortBy, order, decodeCursor(query.sortBy, cursor, backward))",
                                    "afterCursor(query.sortBy, order, decodeCursor(query.sortBy, cursor, backward), backward)")
        if source_path.endswith("projects.controller.ts"):
            controller_imports = ", ".join([
                f"{_camel(one)}ExportQuerySchema", f"{_camel(one)}ListQuerySchema", f"{_camel(one)}Schema",
                f"type {model} as FeatureResponse", f"type {model}ExportQuery as FeatureExportQuery",
                f"type {model}Input as FeatureInput", f"type {model}ListQuery as FeatureListQuery",
            ])
            source = re.sub(r"import \{[^}]+\} from '@app/" + re.escape(plural) + r"-contracts';",
                            f"import {{ {controller_imports} }} from '@app/{plural}-contracts';", source, count=1)
            source = source.replace(
                "import { formatDateTime } from '@app/shared-util';",
                f"import {{ {controller_format_imports} }} from '@app/shared-util';",
            )
        result[PurePosixPath(source_path.replace("projects", plural)).as_posix()] = source
    return result
