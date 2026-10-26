from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any


def _sql(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _prisma(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _template(value: str, **parts: str) -> str:
    for key, part in parts.items():
        value = value.replace("{" + key + "}", part)
    return value


def _column(field: dict[str, Any]) -> str:
    return field.get("column", field["name"] + "Id" if field["kind"] == "link" else field["name"])


def render_schema(
    plural: str,
    one: str,
    fields: list[dict[str, Any]],
    kinds: dict[str, Any],
) -> dict[str, str]:
    """Return the generated Prisma schema and timestamped migration."""
    model = "".join(part[:1].upper() + part[1:] for part in one.replace("-", "_").split("_"))
    schema = plural.replace("-", "_")
    definitions = kinds.get("kinds", kinds)
    table = kinds["table"]
    prisma_fields = [
        '  id                  String   @id @default(dbgenerated("uuidv7()")) @db.Uuid',
        "  organisationId      String   @db.Uuid",
    ]
    for field in fields:
        name, kind_name = _column(field), field["kind"]
        kind = definitions[kind_name]
        base, _, native = kind["prisma"].partition(" ")
        optional = field.get("optional", False) and kind_name != "yes-no"
        declaration = f"{base}{'?' if optional else ''}{' ' + native if native else ''}"
        if kind_name == "yes-no":
            declaration += " @default(false)"
        elif kind_name == "status":
            declaration += f" @default({_prisma(field['options'][0])})"
        prisma_fields.append(f"  {name:<19} {declaration}")
    prisma_fields.extend(
        [
            "  createdAtUtc        DateTime @default(now()) @db.Timestamptz(3)",
            "  updatedAtUtc        DateTime @updatedAt @db.Timestamptz(3)",
            "  createdByAccountId  String   @db.Uuid",
            "  modifiedByAccountId String   @db.Uuid",
            "  deletedAtUtc        DateTime? @db.Timestamptz(3)",
            "  deletedByAccountId  String?  @db.Uuid",
            "",
            '  organisation        Organisation @relation(fields: [organisationId], references: [id], onDelete: Restrict)',
            f'  createdByAccount    Account @relation("{model}CreatedBy", fields: [createdByAccountId], references: [id], onDelete: Restrict)',
            f'  modifiedByAccount   Account @relation("{model}ModifiedBy", fields: [modifiedByAccountId], references: [id], onDelete: Restrict)',
            f'  deletedByAccount    Account? @relation("{model}DeletedBy", fields: [deletedByAccountId], references: [id], onDelete: Restrict)',
            "",
            f'  @@index([organisationId, updatedAtUtc(sort: Desc), id(sort: Desc)], map: "idx_{model}_list")',
        ]
    )
    for field in fields:
        name, kind = _column(field), definitions[field["kind"]]
        if kind.get("filter_index"):
            prisma_fields.append(
                f'  @@index([organisationId, {name}, updatedAtUtc(sort: Desc), id(sort: Desc)], map: "idx_{model}_{name}")'
            )
        if kind.get("search_index"):
            prisma_fields.append(
                f'  @@index([organisationId(ops: raw("uuid_ops")), {name}(ops: raw("gin_trgm_ops"))], type: Gin, map: "idx_{model}_{name}_search")'
            )
        if kind.get("index"):
            prisma_fields.append(f'  @@index([{name}], map: "idx_{model}_{name}_link")')
    prisma_fields.extend(
        [
            f'  @@index([{column}], map: "idx_{model}_{column}")'
            for column in ("createdByAccountId", "modifiedByAccountId", "deletedByAccountId")
        ]
    )
    prisma = "\n".join([f"model {model} {{", *prisma_fields, f'  @@schema("{schema}")', "}"]) + "\n"

    columns = [
        '"id" UUID NOT NULL DEFAULT uuidv7()',
        '"organisationId" UUID NOT NULL',
    ]
    checks = []
    for field in fields:
        name, kind_name = _column(field), field["kind"]
        kind = definitions[kind_name]
        optional = field.get("optional", False) and kind_name != "yes-no"
        declaration = f'"{name}" {kind["sql"]}'
        if not optional:
            declaration += " NOT NULL"
        if kind_name == "yes-no":
            declaration += " DEFAULT false"
        elif kind_name == "status":
            declaration += " DEFAULT " + _sql(field["options"][0])
        columns.append(declaration)
        if kind.get("check"):
            options = ", ".join(_sql(option) for option in field.get("options", []))
            checks.append(_template(kind["check"], table=model, column=name, options=options))

    columns.extend(
        [
            '"createdAtUtc" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP',
            '"updatedAtUtc" TIMESTAMPTZ(3) NOT NULL',
            '"createdByAccountId" UUID NOT NULL',
            '"modifiedByAccountId" UUID NOT NULL',
            '"deletedAtUtc" TIMESTAMPTZ(3)',
            '"deletedByAccountId" UUID',
        ]
    )
    constraints = [
        f'CONSTRAINT "{model}_pkey" PRIMARY KEY ("id")',
        *checks,
        f'CONSTRAINT "{model}_organisationId_fkey" FOREIGN KEY ("organisationId") REFERENCES core."Organisation"("id") ON DELETE RESTRICT ON UPDATE CASCADE',
        f'CONSTRAINT "{model}_createdByAccountId_fkey" FOREIGN KEY ("createdByAccountId") REFERENCES core."Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE',
        f'CONSTRAINT "{model}_modifiedByAccountId_fkey" FOREIGN KEY ("modifiedByAccountId") REFERENCES core."Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE',
        f'CONSTRAINT "{model}_deletedByAccountId_fkey" FOREIGN KEY ("deletedByAccountId") REFERENCES core."Account"("id") ON DELETE RESTRICT ON UPDATE CASCADE',
    ]
    migration = [
        f'CREATE SCHEMA "{schema}";',
        f'SET search_path TO "{schema}", public;',
        f'CREATE TABLE "{schema}"."{model}" (\n    '
        + ",\n    ".join(columns + constraints)
        + "\n);",
        _template(table["list_index"], table=model, schema=schema),
    ]
    for field in fields:
        name, kind = _column(field), definitions[field["kind"]]
        if kind.get("filter_index"):
            migration.append(_template(table["filter_index"], table=model, column=name, schema=schema))
        if kind.get("search_index"):
            migration.append(_template(table["search_index"], table=model, column=name, schema=schema))
        if kind.get("index"):
            migration.append(_template(table["index"], table=model, column=name, schema=schema))
    migration.extend(
        [
            f'CREATE INDEX "idx_{model}_{column}" ON "{schema}"."{model}" ("{column}");'
            for column in ("createdByAccountId", "modifiedByAccountId", "deletedByAccountId")
        ]
    )
    migration.extend(
        [
            _template(table["updated_at_trigger"], table=model),
            _template(table["soft_delete_trigger"], table=model),
            "RESET search_path;",
        ]
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return {
        PurePosixPath("apps/api/prisma/schema", f"{plural}.prisma").as_posix(): prisma,
        PurePosixPath("apps/api/prisma/migrations", f"{timestamp}_{plural}", "migration.sql").as_posix(): "\n".join(migration) + "\n",
    }
