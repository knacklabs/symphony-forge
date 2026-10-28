"""Render the generated Python feature's MCP tools."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.feature_python import (
    STARTER_PYTHON,
    _field_attr,
    _literal,
    _python_rename,
    _public_service,
    _remove_marks,
    _replace_mark,
    _snake,
)


def _tool_fields(fields: list[dict[str, Any]], kinds: dict[str, Any]) -> str:
    concise = [
        _field_attr(field)
        for field in fields
        if kinds["kinds"][field["kind"]].get("column")
    ]
    links = {
        _field_attr(field): field["target"]
        for field in fields
        if field["kind"] == "link"
    }
    label = _field_attr(
        next(field for field in fields if field["kind"] == "text" and not field.get("optional"))
    )
    lines = [
        f"label={_literal(label)},",
        f"concise={concise!r},",
        f"links={links!r},",
        "hide=(),",
    ]
    if links:
        lines.append("resolve=_resolve_link,")
    return "\n".join(lines)


def _link_imports(fields: list[dict[str, Any]], root: Path) -> str:
    targets = sorted({field["target"] for field in fields if field["kind"] == "link"})
    if not targets:
        return ""
    services = {target: _public_service(root, target) for target in targets}
    imports = [
        "from sqlalchemy.orm import Session as DbSession",
        *(f"from app.{_snake(target)} import {service}" for target, service in services.items()),
    ]
    resolver = ["", "", "def _resolve_link(db: DbSession, token: str) -> object:"]
    for target, service in services.items():
        resolver.extend(
            [
                f"    if token == {_literal(target)}:",
                f"        return {service}(db)",
            ]
        )
    resolver.append('    raise ValueError("Unknown linked feature.")')
    return "\n".join([*imports, *resolver])


def render_feature_tools(
    fields: list[dict[str, Any]],
    one: str,
    plural: str,
    kinds: dict[str, Any],
    root: Path,
) -> str:
    template = (STARTER_PYTHON / "apps/api/app/projects/tools.py").read_text(
        encoding="utf-8"
    )
    template = _python_rename(template, one, plural)
    module = _snake(plural)
    template = template.replace(f'feature="{module}"', f'feature="{plural}"')
    template = template.replace(f'api="{module}"', f'api="{plural}"')
    template = _replace_mark(template, "tool-imports", _link_imports(fields, root))
    template = _replace_mark(template, "tool-fields", _tool_fields(fields, kinds))
    return _remove_marks(template)
