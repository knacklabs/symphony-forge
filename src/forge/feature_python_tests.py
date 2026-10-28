"""Render HTTP tests for a copied Python feature."""
from __future__ import annotations

import ast
import json
import re
import textwrap
from pathlib import Path
from typing import Any


def _snake(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return re.sub(r"-+", "_", value).lower()


def _camel(value: str) -> str:
    words = _snake(value).split("_")
    return words[0] + "".join(word[:1].upper() + word[1:] for word in words[1:])


def _literal(value: Any, level: int = 0) -> str:
    if value is None:
        return "None"
    if value is True:
        return "True"
    if value is False:
        return "False"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return repr(value)
    pad = " " * level
    child_pad = " " * (level + 4)
    if isinstance(value, (list, tuple)):
        opening, closing = ("[", "]") if isinstance(value, list) else ("(", ")")
        if not value:
            return opening + closing
        lines = [opening]
        lines.extend(child_pad + _literal(item, level + 4) + "," for item in value)
        lines.append(pad + closing)
        return "\n".join(lines)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for key, item in value.items():
            rendered = _literal(item, level + 4)
            value_lines = rendered.splitlines()
            first = child_pad + _literal(str(key)) + ": " + value_lines[0]
            lines.append(first)
            lines.extend(value_lines[1:])
            lines[-1] += ","
        lines.append(pad + "}")
        return "\n".join(lines)
    raise TypeError(f"Cannot write a test value of type {type(value).__name__}.")


def _field_specs(fields: list[dict[str, Any]], kinds: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    specs = []
    for field in fields:
        kind_name = field["kind"]
        kind = kinds["kinds"][kind_name]
        options = list(field.get("options", []))
        if kind_name == "status" and not options:
            options = [kind["sample"], kind["changed"]]
        sample, changed = _sample_values(kind_name, options, kind)
        specs.append(
            {
                "column": field["column"],
                "kind": kind_name,
                "optional": bool(field.get("optional", False) and kind_name != "yes-no"),
                "options": options,
                "sample": sample,
                "changed": changed,
                "bad": kind["bad"],
                "target": field.get("target"),
                "filterable": bool(kind.get("filter_index")),
                "sortable": kind_name != "long-text",
            }
        )
    return tuple(specs)


def _sample_values(
    kind_name: str, options: list[str], kind: dict[str, Any]
) -> tuple[Any, Any]:
    if kind_name != "status":
        return kind["sample"], kind["changed"]
    sample = kind["sample"] if kind["sample"] in options else options[0]
    changed = kind["changed"]
    if changed not in options or changed == sample:
        changed = next((option for option in options if option != sample), sample)
    return sample, changed


def _is_none_type(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None or (
        isinstance(node, ast.Name) and node.id == "None"
    )


def _without_none(node: ast.expr) -> tuple[ast.expr, bool]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        if _is_none_type(node.left):
            return node.right, True
        if _is_none_type(node.right):
            return node.left, True
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
        if node.value.id == "Optional":
            return node.slice, True
    return node, False


def _field_kind(node: ast.expr, default: ast.expr | None, enums: dict[str, list[str]]) -> tuple[str, list[str]]:
    node, _ = _without_none(node)
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "Literal":
        if isinstance(node.slice, ast.Tuple):
            return "status", [ast.literal_eval(option) for option in node.slice.elts]
        return "status", [ast.literal_eval(node.slice)]
    if isinstance(node, ast.Name) and node.id in enums:
        return "status", enums[node.id]
    name = node.id if isinstance(node, ast.Name) else ""
    types = {
        "Decimal": "number",
        "int": "money",
        "date": "date",
        "bool": "yes-no",
        "UUID": "link",
    }
    if name in types:
        return types[name], []
    if name == "str":
        if isinstance(default, ast.Call) and isinstance(default.func, ast.Name) and default.func.id == "Field":
            keywords = {keyword.arg: ast.literal_eval(keyword.value)
                        for keyword in default.keywords if keyword.arg and isinstance(keyword.value, ast.Constant)}
            if keywords.get("pattern"):
                return "email", []
            if keywords.get("max_length", 0) > 200:
                return "long-text", []
        return "text", []
    return "text", []


def _schema_specs(root: Path, module: str, kinds: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    path = root / "apps/api/app" / _snake(module) / "schema.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    enums: dict[str, list[str]] = {}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(isinstance(base, ast.Name) and base.id in {"Enum", "StrEnum"} for base in node.bases):
            continue
        values = []
        for entry in node.body:
            if isinstance(entry, ast.Assign) and len(entry.targets) == 1 and isinstance(entry.targets[0], ast.Name):
                try:
                    value = ast.literal_eval(entry.value)
                except (ValueError, TypeError):
                    continue
                if isinstance(value, str):
                    values.append(value)
        enums[node.name] = values
    input_model = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name.endswith("Input")
    )
    fields = []
    for node in input_model.body:
        if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
            continue
        attribute = node.target.id
        annotation, optional = _without_none(node.annotation)
        kind_name, options = _field_kind(annotation, node.value, enums)
        if kind_name == "text" and isinstance(node.value, ast.Call):
            keywords = {keyword.arg: ast.literal_eval(keyword.value)
                        for keyword in node.value.keywords if keyword.arg and isinstance(keyword.value, ast.Constant)}
            if keywords.get("max_length") == 10000:
                kind_name = "long-text"
            elif keywords.get("pattern"):
                kind_name = "email"
        kind = kinds["kinds"][kind_name]
        sample, changed = _sample_values(kind_name, options, kind)
        fields.append(
            {
                "column": _camel(attribute),
                "kind": kind_name,
                "optional": bool(optional and kind_name != "yes-no"),
                "options": options,
                "sample": sample,
                "changed": changed,
                "bad": kind["bad"],
                "target": None,
                "filterable": bool(kind.get("filter_index")),
                "sortable": kind_name != "long-text",
            }
        )
    return tuple(fields)


def _existing_specs(root: Path, module: str, kinds: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    test_path = root / "apps/api/tests" / f"test_{_snake(module)}.py"
    if test_path.is_file():
        tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
        for node in tree.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "FEATURE_FIELDS" and node.value is not None:
                    return tuple(ast.literal_eval(node.value))
    return _schema_specs(root, module, kinds)


def _linked_specs(
    root: Path,
    fields: tuple[dict[str, Any], ...],
    kinds: dict[str, Any],
    current_module: str,
) -> dict[str, tuple[dict[str, Any], ...]]:
    result: dict[str, tuple[dict[str, Any], ...]] = {current_module: fields}
    pending = [field["target"] for field in fields if field["kind"] == "link"]
    while pending:
        module = pending.pop()
        if module in result:
            continue
        specs = _existing_specs(root, module, kinds)
        result[module] = specs
        pending.extend(
            field["target"] for field in specs
            if field["kind"] == "link" and field["target"] not in result
        )
    return result


def _marked_helper() -> str:
    source_path = (
        Path(__file__).parent
        / "templates/starter-python/apps/api/tests/test_projects.py"
    )
    source = source_path.read_text(encoding="utf-8")
    start = "# forge:feature:test-helper:start"
    end = "# forge:feature:test-helper:end"
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("The Python starter must mark its reusable feature test helper once.")
    helper = source.split(start, 1)[1].split(end, 1)[0].strip()
    if not helper.startswith("@contextmanager"):
        raise ValueError("The marked Python feature test helper is incomplete.")
    return helper


def render_python_tests(
    fields: list[dict[str, Any]], one: str, plural: str, kinds: dict[str, Any], root: Path
) -> str:
    """Render generated tests at the HTTP boundary, reusing the starter's invite helper."""
    feature_fields = _field_specs(fields, kinds)
    linked_fields = _linked_specs(root, feature_fields, kinds, plural)
    search_field = next(
        field for field in feature_fields if field["kind"] in {"text", "email"}
    )
    name_field = next(
        field for field in feature_fields
        if field["kind"] == "text" and not field["optional"]
    )
    sort_fields = [name_field["column"]]
    sort_fields.extend(
        field["column"] for field in feature_fields
        if field["sortable"] and field is not name_field
    )
    sort_fields.extend(("createdAtUtc", "updatedAtUtc"))
    test_source = textwrap.dedent(
        '''\
        """HTTP contracts for a generated feature against its running app and database."""

        import csv
        from collections.abc import Iterator
        from contextlib import contextmanager
        from decimal import Decimal
        from io import StringIO
        from typing import Any, cast
        from uuid import uuid4

        import httpx
        from test_api import credentials, sign_up
        from test_invites import invite

        FEATURE_PATH = __FEATURE_PATH__
        FEATURE = __FEATURE__
        SINGULAR = __SINGULAR__
        NAME_FIELD = __NAME_FIELD__
        SEARCH_FIELD = __SEARCH_FIELD__
        SEARCH_KIND = __SEARCH_KIND__
        SORT_FIELDS: tuple[str, ...] = __SORT_FIELDS__
        FEATURE_FIELDS: tuple[dict[str, Any], ...] = __FEATURE_FIELDS__
        LINKED_FIELDS: dict[str, tuple[dict[str, Any], ...]] = __LINKED_FIELDS__
        ROUTES: tuple[tuple[str, str, str], ...] = (
            ("GET", "", "view"),
            ("GET", "/export", "view"),
            ("GET", "/{{id}}", "view"),
            ("GET", "/{{id}}/changes", "view"),
            ("POST", "", "create"),
            ("PUT", "/{{id}}", "edit"),
            ("DELETE", "/{{id}}", "delete"),
            ("POST", "/{{id}}/restore", "restore"),
        )


        __MARKED_HELPER__


        def _body(response: httpx.Response) -> dict[str, Any]:
            value = response.json()["data"]
            assert isinstance(value, dict), value
            return cast(dict[str, Any], value)


        def _items(response: httpx.Response) -> list[dict[str, Any]]:
            value = _body(response)["items"]
            assert isinstance(value, list), value
            return cast(list[dict[str, Any]], value)


        def _field_value(
            client: httpx.Client,
            csrf: str,
            field: dict[str, Any],
            *,
            changed: bool,
            index: int,
            seen: tuple[str, ...],
        ) -> Any:
            kind = field["kind"]
            if kind == "link":
                target = field["target"]
                assert isinstance(target, str), field
                return _create_linked(client, csrf, target, index=index, seen=seen)
            if kind == "status":
                options = field["options"]
                assert options
                if changed and field["changed"] != field["sample"]:
                    return field["changed"]
                return options[index % len(options)]
            value = field["changed"] if changed else field["sample"]
            if kind == "text" and index:
                return f"{{value}} {{index}}"
            if kind == "email" and index:
                return f"{{index}}-{{value}}"
            if kind == "number":
                return str(Decimal(str(value)) + index)
            if kind == "money":
                return int(value) + index
            if kind == "yes-no" and index:
                return index % 2 == 0
            return value


        def _payload(
            client: httpx.Client,
            csrf: str,
            fields: tuple[dict[str, Any], ...] = FEATURE_FIELDS,
            *,
            changed: bool = False,
            index: int = 0,
            null_optional: bool = False,
            nested: bool = False,
            seen: tuple[str, ...] = (FEATURE,),
        ) -> dict[str, Any]:
            values: dict[str, Any] = {{}}
            for field in fields:
                column = field["column"]
                if field["optional"] and (null_optional or nested):
                    values[column] = None
                else:
                    values[column] = _field_value(
                        client,
                        csrf,
                        field,
                        changed=changed,
                        index=index,
                        seen=seen,
                    )
            return values


        def _create_linked(
            client: httpx.Client,
            csrf: str,
            target: str,
            *,
            index: int,
            seen: tuple[str, ...],
        ) -> str:
            assert target not in seen, (target, seen)
            fields = LINKED_FIELDS[target]
            response = client.post(
                f"/api/v1/{{target}}",
                headers={{"x-csrf-token": csrf}},
                json=_payload(
                    client,
                    csrf,
                    fields,
                    index=index,
                    nested=True,
                    seen=(*seen, target),
                ),
            )
            assert response.status_code == 201, response.text
            item_id = _body(response)["id"]
            assert isinstance(item_id, str), item_id
            return item_id


        def _create(
            client: httpx.Client,
            csrf: str,
            body: dict[str, Any] | None = None,
            *,
            index: int = 0,
            null_optional: bool = False,
        ) -> dict[str, Any]:
            if body is None:
                body = _payload(client, csrf, index=index, null_optional=null_optional)
            response = client.post(
                FEATURE_PATH,
                headers={{"x-csrf-token": csrf}},
                json=body,
            )
            assert response.status_code == 201, response.text
            return _body(response)


        def _list(client: httpx.Client, **params: str) -> dict[str, Any]:
            response = client.get(FEATURE_PATH, params=params)
            assert response.status_code == 200, response.text
            return _body(response)


        def _route_request(
            client: httpx.Client,
            method: str,
            path: str,
            active_id: str,
            deleted_id: str,
            body: dict[str, Any],
        ) -> httpx.Response:
            identifier = deleted_id if "restore" in path else active_id
            url = FEATURE_PATH + path.replace("{{id}}", identifier)
            params = {{"deleted": "yes"}} if path in {{"", "/export"}} else None
            headers = {{"x-csrf-token": client.cookies["starter_csrf"]}}
            values = body if method in {{"POST", "PUT"}} and path != "/{{id}}/restore" else None
            return client.request(
                method,
                url,
                params=params,
                headers=headers if method in {{"POST", "PUT", "DELETE"}} else None,
                json=values,
            )


        # Audit: this protects CRUD and retained soft-deleted records over HTTP. A wrong route,
        # missing audit response, or hard delete breaks the real API contract; command text
        # checks cannot observe it. The running app and database own this behavior.
        def test_creates_lists_reads_updates_and_deletes_a___ONE__(client: httpx.Client) -> None:
            account, csrf = sign_up(client)
            created = _create(client, csrf, index=1)
            item_id = created["id"]
            assert created["createdByEmail"] == account["email"]
            assert created["modifiedByEmail"] == account["email"]

            listed = _list(client, limit="20", sortBy=NAME_FIELD, sortOrder="asc")
            assert [item["id"] for item in listed["items"]] == [item_id]
            assert listed["paging"]["total"] == 1
            assert listed["paging"]["nextCursor"] is None
            assert listed["paging"]["previousCursor"] is None
            read = client.get(f"{{FEATURE_PATH}}/{{item_id}}")
            assert read.status_code == 200, read.text
            assert _body(read)["id"] == item_id

            changed = _payload(client, csrf, changed=True, index=2)
            updated = client.put(
                f"{{FEATURE_PATH}}/{{item_id}}",
                headers={{"x-csrf-token": csrf}},
                json=changed,
            )
            assert updated.status_code == 200, updated.text
            assert _body(updated)[NAME_FIELD] == changed[NAME_FIELD]
            removed = client.delete(
                f"{{FEATURE_PATH}}/{{item_id}}", headers={{"x-csrf-token": csrf}}
            )
            assert removed.status_code == 200, removed.text
            assert removed.json() == {{"success": True, "data": None, "error": None}}
            deleted = _body(client.get(f"{{FEATURE_PATH}}/{{item_id}}"))
            assert deleted["deletedAtUtc"] is not None
            assert item_id not in [item["id"] for item in _list(client)["items"]]
            restored_list = _list(client, deleted="yes")
            assert item_id in [item["id"] for item in restored_list["items"]]


        # Audit: this rejects whitespace-only names after input trimming. The generic bad-value
        # case checks the empty string, so it would miss a validator that accepts spaces.
        # It uses the real API and needs no production test seam.
        def test_rejects_a_whitespace_only___NAME_FIELD_SNAKE__(client: httpx.Client) -> None:
            _, csrf = sign_up(client)
            body = _payload(client, csrf)
            body[NAME_FIELD] = "   "
            refused = client.post(
                FEATURE_PATH,
                headers={{"x-csrf-token": csrf}},
                json=body,
            )
            assert refused.status_code == 400, refused.text
            errors = refused.json()["error"]["details"]["fieldErrors"]
            assert any(error["field"] == NAME_FIELD for error in errors)


        # Audit: this protects every advertised sort cursor, including null optional fields.
        # A cursor that drops or repeats tied/null rows fails even if page one looks right;
        # other tests do not cross each sort field and null state through HTTP.
        def test_pages___PLURAL___with_next_and_previous_cursors(client: httpx.Client) -> None:
            _, csrf = sign_up(client)
            created_ids = [
                _create(client, csrf, index=index, null_optional=index % 2 == 0)["id"]
                for index in range(5)
            ]
            for sort_by in SORT_FIELDS:
                for sort_order in ("asc", "desc"):
                    params = {{"limit": "2", "sortBy": sort_by, "sortOrder": sort_order}}
                    page = _list(client, **params)
                    pages = [page]
                    while page["paging"]["nextCursor"] is not None:
                        params["after"] = page["paging"]["nextCursor"]
                        page = _list(client, **params)
                        pages.append(page)
                        assert len(pages) <= len(created_ids)
                    item_ids = [item["id"] for result in pages for item in result["items"]]
                    assert len(item_ids) == len(created_ids)
                    assert len(set(item_ids)) == len(created_ids)
                    assert set(item_ids) == set(created_ids)
                    assert pages[-1]["paging"]["nextCursor"] is None
                    assert pages[-1]["paging"]["total"] == len(created_ids)
                    if len(pages) > 1:
                        previous = pages[-1]["paging"]["previousCursor"]
                        assert previous is not None
                        back = _list(
                            client,
                            limit="2",
                            sortBy=sort_by,
                            sortOrder=sort_order,
                            before=previous,
                        )
                        assert [item["id"] for item in back["items"]] == [
                            item["id"] for item in pages[-2]["items"]
                        ]


        # Audit: this protects search, each field filter, and filtered CSV at the HTTP boundary.
        # A missing predicate or an export that ignores the list filters changes visible data;
        # the starter projects tests do not cover this generated field set.
        def test_filters___PLURAL___by_search_and_filters(client: httpx.Client) -> None:
            _, csrf = sign_up(client)
            matching_ids = []
            for index in range(3):
                body = _payload(client, csrf, index=index)
                if SEARCH_KIND == "email":
                    body[SEARCH_FIELD] = (
                        f"needle-{{index}}@example.test"
                        if index < 2
                        else "other@example.test"
                    )
                else:
                    body[SEARCH_FIELD] = (
                        f"Needle record {{index}}" if index < 2 else "Other record"
                    )
                matching_ids.append(_create(client, csrf, body)["id"])
            found = _list(client, search="NEEDLE", sortBy=NAME_FIELD, sortOrder="asc")
            assert len(found["items"]) == 2
            assert {{item["id"] for item in found["items"]}} == set(matching_ids[:2])

            export = client.get(f"{{FEATURE_PATH}}/export", params={{"search": "needle"}})
            assert export.status_code == 200, export.text
            assert "needle" in export.text.lower()
            unmatched = "other@example.test" if SEARCH_KIND == "email" else "Other record"
            assert unmatched not in export.text

            for field in FEATURE_FIELDS:
                if not field["filterable"]:
                    continue
                kind = field["kind"]
                needle = f"filter-{{field['column']}}"
                rows = []
                for index in range(2):
                    body = _payload(client, csrf, index=index + 10)
                    if SEARCH_KIND == "email":
                        body[SEARCH_FIELD] = f"{{needle}}-{{index}}@example.test"
                    else:
                        body[SEARCH_FIELD] = f"{{needle}} row {{index}}"
                    if kind == "status":
                        options = field["options"]
                        body[field["column"]] = options[0 if index == 0 else -1]
                        query_value = options[0]
                        expected = 2 if len(options) == 1 else 1
                    elif kind == "yes-no":
                        body[field["column"]] = index == 0
                        query_value = "yes"
                        expected = 1
                    elif kind == "link":
                        expected = 1
                    else:
                        raise AssertionError(f"Unsupported filter field: {{field}}")
                    rows.append(_create(client, csrf, body))
                if kind == "link":
                    query_value = rows[0][field["column"]]
                filtered = _list(
                    client,
                    search=needle,
                    **{{field["column"]: str(query_value)}},
                )
                assert len(filtered["items"]) == expected
                if kind != "status" or len(field["options"]) > 1:
                    assert filtered["items"][0]["id"] == rows[0]["id"]
                exported = client.get(
                    f"{{FEATURE_PATH}}/export",
                    params={{"search": needle, field["column"]: str(query_value)}},
                )
                assert exported.status_code == 200, exported.text
                assert len(list(csv.reader(StringIO(exported.text)))) == expected + 1


        # Audit: this protects organisation scoping on lists, export and each item route. A
        # module query that omits the caller's organisation can expose or change another team's
        # data; schema and unit checks cannot observe the public HTTP boundary.
        def test_keeps_another_organisation_from_reading_or_changing_a___ONE__(
            client: httpx.Client,
        ) -> None:
            _, csrf = sign_up(client)
            owned = _create(client, csrf, index=1)
            owned_id = owned["id"]
            with httpx.Client(base_url=client.base_url, timeout=15) as other:
                _, other_csrf = sign_up(other)
                assert _list(other, deleted="yes")["items"] == []
                exported = other.get(f"{{FEATURE_PATH}}/export", params={{"deleted": "yes"}})
                assert exported.status_code == 200, exported.text
                assert owned[NAME_FIELD] not in exported.text
                for path in (f"/{{owned_id}}", f"/{{owned_id}}/changes"):
                    refused = other.get(FEATURE_PATH + path)
                    assert refused.status_code == 404, refused.text
                changed = _payload(other, other_csrf, changed=True, index=2)
                for method, path, body in (
                    ("PUT", f"/{{owned_id}}", changed),
                    ("DELETE", f"/{{owned_id}}", None),
                    ("POST", f"/{{owned_id}}/restore", None),
                ):
                    refused = other.request(
                        method,
                        FEATURE_PATH + path,
                        headers={{"x-csrf-token": other_csrf}},
                        json=body,
                    )
                    assert refused.status_code == 404, refused.text
                created_elsewhere = _create(other, other_csrf, index=3)
                hidden = client.get(f"{{FEATURE_PATH}}/{{created_elsewhere['id']}}")
                assert hidden.status_code == 404, hidden.text
                assert owned_id not in [item["id"] for item in _list(other)["items"]]


        # Audit: this protects validation of every field, including numeric values whose shape
        # is valid but whose precision or range cannot be stored. Existing bad samples do not
        # cover those persistence failures; the live API and database path is the owner, with no
        # production seam.
        def test_rejects_bad_fields_unknown_inputs_and_unknown_list_parameters(
            client: httpx.Client,
        ) -> None:
            _, csrf = sign_up(client)
            valid = _payload(client, csrf)
            for field in FEATURE_FIELDS:
                body = dict(valid)
                bad = field["bad"]
                if field["kind"] == "status":
                    bad = f"{{field['options'][0]}}-invalid"
                body[field["column"]] = bad
                refused = client.post(
                    FEATURE_PATH,
                    headers={{"x-csrf-token": csrf}},
                    json=body,
                )
                assert refused.status_code == 400, (field, refused.text)
                assert refused.json()["error"]["code"] == "VALIDATION_ERROR"
                assert refused.json()["error"]["details"]["fieldErrors"]
                if field["kind"] == "link":
                    body[field["column"]] = str(uuid4())
                    missing = client.post(
                        FEATURE_PATH,
                        headers={{"x-csrf-token": csrf}},
                        json=body,
                    )
                    assert missing.status_code == 400, missing.text
                    assert missing.json()["error"]["code"] == "VALIDATION_ERROR"

            invalid_numeric_values = {{
                "number": ("1.23456", "1000000000000000"),
                "money": (2147483648, -2147483649),
            }}
            for field in FEATURE_FIELDS:
                for bad in invalid_numeric_values.get(field["kind"], ()):
                    body = dict(valid)
                    body[field["column"]] = bad
                    refused = client.post(
                        FEATURE_PATH,
                        headers={{"x-csrf-token": csrf}},
                        json=body,
                    )
                    assert refused.status_code == 400, (field, bad, refused.text)
                    assert refused.json()["error"]["code"] == "VALIDATION_ERROR"
                    errors = refused.json()["error"]["details"]["fieldErrors"]
                    assert any(error["field"] == field["column"] for error in errors)

            extra = dict(valid)
            extra["unexpected"] = True
            refused = client.post(
                FEATURE_PATH, headers={{"x-csrf-token": csrf}}, json=extra
            )
            assert refused.status_code == 400, refused.text
            assert refused.json()["error"]["code"] == "VALIDATION_ERROR"
            unknown_query = client.get(FEATURE_PATH, params={{"futureFilter": "value"}})
            assert unknown_query.status_code == 400, unknown_query.text
            assert unknown_query.json()["error"]["code"] == "VALIDATION_ERROR"
            invalid_sort = client.get(FEATURE_PATH, params={{"sortBy": "notAField"}})
            assert invalid_sort.status_code == 400, invalid_sort.text
            assert invalid_sort.json()["error"]["code"] == "VALIDATION_ERROR"


        # Audit: this protects authentication and CSRF at the real route boundary. A route that
        # writes before either check can be called by an anonymous or cross-site request; no
        # schema or source assertion can prove the middleware path.
        def test_requires_sign_in_and_csrf_before___PLURAL___changes(
            client: httpx.Client,
        ) -> None:
            anonymous = client.get(FEATURE_PATH)
            assert anonymous.status_code == 401, anonymous.text
            assert anonymous.json()["error"]["code"] == "UNAUTHENTICATED"
            _, csrf = sign_up(client)
            body = _payload(client, csrf)
            active = _create(client, csrf, body)
            deleted = _create(client, csrf, _payload(client, csrf, index=1))
            deleted_path = f"{{FEATURE_PATH}}/{{deleted['id']}}"
            removed = client.delete(deleted_path, headers={{"x-csrf-token": csrf}})
            assert removed.status_code == 200, removed.text
            for response in (
                client.post(FEATURE_PATH, json=body),
                client.post(
                    FEATURE_PATH,
                    headers={{"x-csrf-token": csrf + "wrong"}},
                    json=body,
                ),
                client.put(
                    f"{{FEATURE_PATH}}/{{active['id']}}",
                    headers={{"x-csrf-token": csrf + "wrong"}},
                    json=body,
                ),
                client.delete(
                    f"{{FEATURE_PATH}}/{{active['id']}}",
                    headers={{"x-csrf-token": csrf + "wrong"}},
                ),
                client.post(
                    deleted_path + "/restore",
                    headers={{"x-csrf-token": csrf + "wrong"}},
                ),
            ):
                assert response.status_code == 403, response.text
                assert response.json()["error"]["code"] == "CSRF_CHECK_FAILED"
            assert client.get(f"{{FEATURE_PATH}}/{{active['id']}}").status_code == 200


        # Audit: this protects the CSV formula guard through the generated export route. A
        # spreadsheet formula in a text field executes when opened; other feature tests do not
        # verify CSV cell contents after the public endpoint serializes them.
        def test_keeps_formula_leading_text_safe_in_csv(client: httpx.Client) -> None:
            _, csrf = sign_up(client)
            body = _payload(client, csrf)
            formula_field = next(field for field in FEATURE_FIELDS if field["kind"] == "text")
            body[formula_field["column"]] = "=1+1"
            created = _create(client, csrf, body)
            response = client.get(f"{{FEATURE_PATH}}/export")
            assert response.status_code == 200, response.text
            rows = list(csv.reader(StringIO(response.text)))
            assert len(rows) == 2
            assert "'=1+1" in rows[1]
            assert created[NAME_FIELD]


        # Audit: this protects all four transactional history actions and confirms an unchanged
        # replacement adds no row. A missing or duplicate history write loses the audit trail;
        # the detail and history APIs are the real owners of this contract.
        def test_records_each___ONE___change_in_the_change_history(
            client: httpx.Client,
        ) -> None:
            account, csrf = sign_up(client)
            created_body = _payload(client, csrf, index=31)
            created_body[NAME_FIELD] = f"History {{SINGULAR}} original"
            created = _create(client, csrf, created_body)
            item_id = created["id"]
            changed_body = _payload(client, csrf, changed=True, index=0)
            changed_body[NAME_FIELD] = f"History {{SINGULAR}} changed"
            path = f"{{FEATURE_PATH}}/{{item_id}}"
            changed = client.put(
                path,
                headers={{"x-csrf-token": csrf}},
                json=changed_body,
            )
            assert changed.status_code == 200, changed.text
            same = client.put(
                path,
                headers={{"x-csrf-token": csrf}},
                json=changed_body,
            )
            assert same.status_code == 200, same.text
            changes_path = path + "/changes"
            changes = client.get(changes_path)
            assert changes.status_code == 200, changes.text
            assert len(changes.json()["data"]) == 2
            assert changes.json()["data"][0]["summary"]
            assert "changed from" in changes.json()["data"][0]["summary"]
            assert changes.json()["data"][1]["summary"] == f"Created the {{SINGULAR}}"
            history_entries = changes.json()["data"]
            assert all(entry["actorEmail"] == account["email"] for entry in history_entries)

            deleted = client.delete(path, headers={{"x-csrf-token": csrf}})
            assert deleted.status_code == 200, deleted.text
            restored = client.post(
                path + "/restore", headers={{"x-csrf-token": csrf}}
            )
            assert restored.status_code == 200, restored.text
            summaries = [entry["summary"] for entry in client.get(changes_path).json()["data"]]
            assert summaries[0] == f"Restored the {{SINGULAR}}"
            assert summaries[1] == f"Deleted the {{SINGULAR}}"
            assert "changed from" in summaries[2]
            assert summaries[3] == f"Created the {{SINGULAR}}"

            history = client.get("/api/v1/history")
            assert history.status_code == 200, history.text
            history_summaries = [entry["summary"] for entry in history.json()["data"]]
            assert f"{{created_body[NAME_FIELD]}}: Created the {{SINGULAR}}" in history_summaries
            assert any(
                summary.startswith(f"{{changed_body[NAME_FIELD]}}: ")
                and "changed from" in summary
                for summary in history_summaries
            )
            assert f"{{changed_body[NAME_FIELD]}}: Deleted the {{SINGULAR}}" in history_summaries
            assert f"{{changed_body[NAME_FIELD]}}: Restored the {{SINGULAR}}" in history_summaries


        # Audit: this protects each route's permission against the member's live list.
        # A route guarded by the wrong action can expose data or allow a denied write; static
        # checks cannot prove FastAPI dependencies execute on real requests.
        def test_each___PLURAL___endpoint_refuses_a_member_without_its_permission(
            client: httpx.Client,
        ) -> None:
            _, csrf = sign_up(client)
            admin_active = _create(client, csrf, index=41)
            admin_deleted = _create(client, csrf, index=42)
            deleted_id = admin_deleted["id"]
            assert client.delete(
                f"{{FEATURE_PATH}}/{{deleted_id}}", headers={{"x-csrf-token": csrf}}
            ).status_code == 200
            member_active = _create(client, csrf, index=43)
            member_deleted = _create(client, csrf, index=44)
            member_deleted_id = member_deleted["id"]
            assert client.delete(
                f"{{FEATURE_PATH}}/{{member_deleted_id}}",
                headers={{"x-csrf-token": csrf}},
            ).status_code == 200
            route_body = _payload(client, csrf)
            for method, path, _permission in ROUTES:
                response = _route_request(
                    client, method, path, admin_active["id"], deleted_id, route_body
                )
                assert response.status_code != 403, (method, path, response.text)

            with joined_member(client, csrf) as member:
                me = member.get("/api/v1/auth/me")
                assert me.status_code == 200, me.text
                permissions = set(me.json()["data"]["permissions"])
                for method, path, permission in ROUTES:
                    response = _route_request(
                        member,
                        method,
                        path,
                        member_active["id"],
                        member_deleted_id,
                        route_body,
                    )
                    if f"{{FEATURE}}.{{permission}}" in permissions:
                        assert response.status_code != 403, (method, path, response.text)
                    else:
                        assert response.status_code == 403, (method, path, response.text)
                        assert response.json()["error"]["code"] == "PERMISSION_DENIED"


        # Audit: this protects deleted-row visibility and admin restore through the API.
        # A member-visible deleted row or restore without a history record breaks the accepted
        # permission contract; the running API is the owning boundary.
        def test_an_admin_restores_a_deleted___ONE__(client: httpx.Client) -> None:
            admin, csrf = sign_up(client)
            keep = _create(client, csrf, index=51)
            gone = _create(client, csrf, index=52)
            gone_id = gone["id"]
            gone_path = f"{{FEATURE_PATH}}/{{gone_id}}"
            removed = client.delete(gone_path, headers={{"x-csrf-token": csrf}})
            assert removed.status_code == 200, removed.text
            member_gone = _create(client, csrf, index=53)
            member_gone_id = member_gone["id"]
            member_gone_path = f"{{FEATURE_PATH}}/{{member_gone_id}}"
            member_removed = client.delete(
                member_gone_path, headers={{"x-csrf-token": csrf}}
            )
            assert member_removed.status_code == 200, member_removed.text
            all_items = _list(client, deleted="yes")
            deleted_item = next(item for item in all_items["items"] if item["id"] == gone_id)
            assert deleted_item["deletedAtUtc"] is not None
            assert deleted_item["deletedByEmail"] == admin["email"]
            assert gone_id not in [item["id"] for item in _list(client)["items"]]

            with joined_member(client, csrf) as member:
                me = member.get("/api/v1/auth/me")
                assert me.status_code == 200, me.text
                permissions = set(me.json()["data"]["permissions"])
                if f"{{FEATURE}}.view" in permissions:
                    member_list = member.get(FEATURE_PATH, params={{"deleted": "yes"}})
                    assert member_list.status_code == 200, member_list.text
                    visible = [item["id"] for item in member_list.json()["data"]["items"]]
                    if f"{{FEATURE}}.restore" in permissions:
                        assert {{gone_id, member_gone_id}} <= set(visible)
                        assert member.get(gone_path).status_code == 200
                        assert member.get(member_gone_path).status_code == 200
                    else:
                        assert gone_id not in visible
                        assert member_gone_id not in visible
                        hidden = member.get(gone_path)
                        assert hidden.status_code == 404, hidden.text
                        hidden_member_item = member.get(member_gone_path)
                        assert hidden_member_item.status_code == 404, hidden_member_item.text
                    exported = member.get(
                        f"{{FEATURE_PATH}}/export", params={{"deleted": "yes"}}
                    )
                    assert exported.status_code == 200, exported.text
                    if f"{{FEATURE}}.restore" not in permissions:
                        assert gone[NAME_FIELD] not in exported.text
                        assert member_gone[NAME_FIELD] not in exported.text
                else:
                    denied_list = member.get(FEATURE_PATH, params={{"deleted": "yes"}})
                    assert denied_list.status_code == 403, denied_list.text
                    assert denied_list.json()["error"]["code"] == "PERMISSION_DENIED"
                    assert member.get(gone_path).status_code == 403

                member_csrf = member.cookies["starter_csrf"]
                restore = member.post(
                    member_gone_path + "/restore",
                    headers={{"x-csrf-token": member_csrf}},
                )
                if f"{{FEATURE}}.restore" in permissions:
                    assert restore.status_code == 200, restore.text
                else:
                    assert restore.status_code == 403, restore.text

            restored = client.post(
                gone_path + "/restore", headers={{"x-csrf-token": csrf}}
            )
            assert restored.status_code == 200, restored.text
            assert _body(restored)["deletedAtUtc"] is None
            recent_changes = client.get(gone_path + "/changes").json()["data"][:2]
            assert [entry["summary"] for entry in recent_changes] == [
                f"Restored the {{SINGULAR}}",
                f"Deleted the {{SINGULAR}}",
            ]
            assert keep["id"] in [item["id"] for item in _list(client)["items"]]
            again = client.post(gone_path + "/restore", headers={{"x-csrf-token": csrf}})
            assert again.status_code == 404, again.text
        '''
    ).format()
    replacements = {
        "__FEATURE_PATH__": _literal(f"/api/v1/{plural}"),
        "__FEATURE__": _literal(plural),
        "__SINGULAR__": _literal(one.replace("-", " ")),
        "__NAME_FIELD__": _literal(name_field["column"]),
        "__SEARCH_FIELD__": _literal(search_field["column"]),
        "__SEARCH_KIND__": _literal(search_field["kind"]),
        "__NAME_FIELD_SNAKE__": _snake(name_field["column"]),
        "__SORT_FIELDS__": _literal(tuple(sort_fields)),
        "__FEATURE_FIELDS__": _literal(feature_fields),
        "__LINKED_FIELDS__": _literal(linked_fields, 0),
        "__MARKED_HELPER__": _marked_helper(),
        "__ONE__": _snake(one),
        "__PLURAL__": _snake(plural),
    }
    for token, value in replacements.items():
        test_source = test_source.replace(token, value)
    return test_source
