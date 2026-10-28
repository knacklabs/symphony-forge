"""The projects list, its paging and its filters at the HTTP boundary.

Audit: these cases own the projects API contracts, the twins of the React starter's
projects suite: CRUD, keyset paging with next and previous cursors, search and the
status filter. All data enters through HTTP against the running app and database.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import httpx
from test_api import credentials, sign_up
from test_invites import invite


def create_projects(
    client: httpx.Client, csrf: str, projects: list[tuple[str, str]]
) -> None:
    for name, status in projects:
        response = client.post(
            "/api/v1/projects",
            headers={"x-csrf-token": csrf},
            json={"name": name, "status": status},
        )
        assert response.status_code == 201, response.text


def list_projects(client: httpx.Client, query: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/projects?{query}")
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()["data"]
    return data


def names(data: dict[str, Any]) -> list[str]:
    return [project["name"] for project in data["items"]]


def test_creates_lists_reads_updates_and_deletes_a_project(
    client: httpx.Client,
) -> None:
    _, csrf = sign_up(client)
    headers = {"x-csrf-token": csrf}
    created = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "First project", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["data"]["id"]
    listed = client.get("/api/v1/projects?limit=20&sortBy=name&sortOrder=asc")
    assert listed.status_code == 200, listed.text
    assert listed.json()["data"]["items"] == [created.json()["data"]]
    assert listed.json()["data"]["paging"] == {
        "limit": 20,
        "nextCursor": None,
        "previousCursor": None,
        "total": 1,
        "totalCapped": False,
    }
    assert (
        client.get(f"/api/v1/projects/{project_id}").json()["data"]["id"] == project_id
    )
    updated = client.put(
        f"/api/v1/projects/{project_id}",
        headers=headers,
        json={"name": "Renamed project", "status": "archived"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["name"] == "Renamed project"
    assert updated.json()["data"]["status"] == "archived"
    deleted = client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"success": True, "data": None, "error": None}
    # An admin still reads a deleted project; the list no longer holds it.
    read = client.get(f"/api/v1/projects/{project_id}")
    assert read.status_code == 200, read.text
    assert read.json()["data"]["deletedAtUtc"] is not None
    assert names(list_projects(client, "")) == []


def test_rejects_a_whitespace_only_project_name(client: httpx.Client) -> None:
    _, csrf = sign_up(client)
    response = client.post(
        "/api/v1/projects",
        headers={"x-csrf-token": csrf},
        json={"name": "   ", "status": "active"},
    )
    assert response.status_code == 400, response.text
    assert any(
        field["field"] == "name"
        for field in response.json()["error"]["details"]["fieldErrors"]
    )


def test_requires_sign_in_and_csrf_before_project_changes(client: httpx.Client) -> None:
    response = client.get("/api/v1/projects")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    _, csrf = sign_up(client)
    project = {"name": "No token", "status": "active"}
    assert client.post("/api/v1/projects", json=project).status_code == 403
    response = client.post(
        "/api/v1/projects", json=project, headers={"x-csrf-token": csrf + "wrong"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_CHECK_FAILED"


def test_pages_projects_with_next_and_previous_cursors(client: httpx.Client) -> None:
    _, csrf = sign_up(client)
    create_projects(
        client,
        csrf,
        [(name, "active") for name in ("Alpha", "Bravo", "Charlie", "Delta", "Echo")],
    )

    # The default order is the last change, newest first.
    assert names(list_projects(client, "")) == [
        "Echo",
        "Delta",
        "Charlie",
        "Bravo",
        "Alpha",
    ]

    by_name = "limit=2&sortBy=name&sortOrder=asc"
    first = list_projects(client, by_name)
    assert names(first) == ["Alpha", "Bravo"]
    assert first["paging"]["previousCursor"] is None
    assert first["paging"]["total"] == 5
    assert first["paging"]["totalCapped"] is False
    second = list_projects(client, f"{by_name}&after={first['paging']['nextCursor']}")
    assert names(second) == ["Charlie", "Delta"]
    last = list_projects(client, f"{by_name}&after={second['paging']['nextCursor']}")
    assert names(last) == ["Echo"]
    assert last["paging"]["nextCursor"] is None

    back = list_projects(client, f"{by_name}&before={last['paging']['previousCursor']}")
    assert names(back) == ["Charlie", "Delta"]
    assert back["paging"]["nextCursor"] is not None
    start = list_projects(
        client, f"{by_name}&before={back['paging']['previousCursor']}"
    )
    assert names(start) == ["Alpha", "Bravo"]
    assert start["paging"]["previousCursor"] is None

    descending = list_projects(client, "limit=2&sortBy=name&sortOrder=desc")
    following = list_projects(
        client,
        "limit=2&sortBy=name&sortOrder=desc"
        f"&after={descending['paging']['nextCursor']}",
    )
    assert names(following) == ["Charlie", "Bravo"]

    # A cursor of another sort, both cursors, or an unreadable cursor gets a field error.
    cursor = first["paging"]["nextCursor"]
    for query, field in (
        (f"sortBy=status&after={cursor}", "after"),
        (f"after={cursor}&before={cursor}", "before"),
        ("after=not+a+cursor", "after"),
        ("before=bm90LWpzb24", "before"),
    ):
        refused = client.get(f"/api/v1/projects?{query}")
        assert refused.status_code == 400, refused.text
        assert refused.json()["error"]["code"] == "VALIDATION_ERROR"
        fields = refused.json()["error"]["details"]["fieldErrors"]
        assert [error["field"] for error in fields] == [field]

    # A cursor holds the whole name, so a full-length name in any script must still page.
    long_names = ["项" * 119 + letter for letter in ("A", "B")]
    create_projects(client, csrf, [(name, "active") for name in long_names])
    by_long_name = "limit=1&sortBy=name&sortOrder=asc&search=%E9%A1%B9"
    long_first = list_projects(client, by_long_name)
    assert names(long_first) == [long_names[0]]
    long_next = list_projects(
        client, f"{by_long_name}&after={long_first['paging']['nextCursor']}"
    )
    assert names(long_next) == [long_names[1]]


def test_filters_projects_by_search_and_filters(client: httpx.Client) -> None:
    _, csrf = sign_up(client)
    create_projects(
        client,
        csrf,
        [
            ("Website redesign", "active"),
            ("Website audit", "archived"),
            ("Mobile app", "active"),
        ],
    )

    def listed(query: str) -> dict[str, Any]:
        return list_projects(client, f"sortBy=name&sortOrder=asc&{query}")

    assert names(listed("search=WEBSITE")) == ["Website audit", "Website redesign"]
    assert names(listed("search=%20site%20")) == ["Website audit", "Website redesign"]
    assert names(listed("status=active")) == ["Mobile app", "Website redesign"]
    both = listed("search=website&status=archived")
    assert names(both) == ["Website audit"]
    assert both["paging"]["total"] == 1
    # Export CSV downloads what the list shows: the same search and filter.
    exported = client.get("/api/v1/projects/export?search=website&status=archived")
    assert exported.status_code == 200, exported.text
    assert "Website audit" in exported.text
    assert "Website redesign" not in exported.text
    assert "Mobile app" not in exported.text
    # The search text is literal: a % or _ does not match every name.
    assert names(listed("search=%25")) == []
    assert names(listed("search=_")) == []

    for query, field in (("status=gone", "status"), ("search=" + "a" * 201, "search")):
        refused = client.get(f"/api/v1/projects?{query}")
        assert refused.status_code == 400, refused.text
        fields = refused.json()["error"]["details"]["fieldErrors"]
        assert [error["field"] for error in fields] == [field]


FIRST_CHANGE = (
    "Name changed from Website redesign to Website relaunch; "
    "Status changed from active to archived"
)


def test_records_each_project_change_in_the_change_history(
    client: httpx.Client,
) -> None:
    # Audit: the twin of the React case. Each create, change and delete must write one
    # Change history row in the same commit, a replace that changes nothing writes none,
    # the changes route lists the newest 5 of this project only, and the organisation-wide
    # history names the project. Real HTTP and Postgres; no production test seam.
    owner, csrf = sign_up(client)
    headers = {"x-csrf-token": csrf}
    created = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Website redesign", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project = created.json()["data"]
    assert project["createdByEmail"] == project["modifiedByEmail"] == owner["email"]
    path = f"/api/v1/projects/{project['id']}"
    # A second project's changes come between this project's changes and must stay out of its list.
    mobile = client.post(
        "/api/v1/projects",
        headers=headers,
        json={"name": "Mobile app", "status": "active"},
    )
    assert mobile.status_code == 201, mobile.text
    other_path = f"/api/v1/projects/{mobile.json()['data']['id']}"
    archived = client.put(
        other_path, headers=headers, json={"name": "Mobile app", "status": "archived"}
    )
    assert archived.status_code == 200, archived.text
    for _ in range(2):  # The second replace changes nothing and adds no row.
        replaced = client.put(
            path,
            headers=headers,
            json={"name": "Website relaunch", "status": "archived"},
        )
        assert replaced.status_code == 200, replaced.text

    changes = client.get(f"{path}/changes")
    assert changes.status_code == 200, changes.text
    assert [
        (entry["actorEmail"], entry["summary"]) for entry in changes.json()["data"]
    ] == [
        (owner["email"], FIRST_CHANGE),
        (owner["email"], "Created the project"),
    ]
    assert set(changes.json()["data"][0]) == {
        "id",
        "actorEmail",
        "summary",
        "createdAtUtc",
    }

    # The detail screen lists the newest 5 changes only.
    for name in ("Second", "Third", "Fourth", "Fifth"):
        renamed = client.put(
            path, headers=headers, json={"name": name, "status": "archived"}
        )
        assert renamed.status_code == 200, renamed.text
    recent = client.get(f"{path}/changes").json()["data"]
    assert [entry["summary"] for entry in recent] == [
        "Name changed from Fourth to Fifth",
        "Name changed from Third to Fourth",
        "Name changed from Second to Third",
        "Name changed from Website relaunch to Second",
        FIRST_CHANGE,
    ]

    deleted = client.delete(path, headers=headers)
    assert deleted.status_code == 200, deleted.text
    # The Change history screen names the project each change was made to.
    history = client.get("/api/v1/history").json()["data"]
    assert [entry["summary"] for entry in history] == [
        "Fifth: Deleted the project",
        "Fifth: Name changed from Fourth to Fifth",
        "Fourth: Name changed from Third to Fourth",
        "Third: Name changed from Second to Third",
        "Second: Name changed from Website relaunch to Second",
        f"Website relaunch: {FIRST_CHANGE}",
        "Mobile app: Status changed from active to archived",
        "Mobile app: Created the project",
        "Website redesign: Created the project",
    ]
    assert [
        entry["summary"] for entry in client.get(f"{other_path}/changes").json()["data"]
    ] == ["Status changed from active to archived", "Created the project"]
    exported = client.get("/api/v1/history/export")
    assert f",{owner['email']},Fifth: Deleted the project" in exported.text

    # An admin still reads a deleted project's changes; another organisation's are not found.
    deleted_changes = client.get(f"{path}/changes")
    assert deleted_changes.status_code == 200, deleted_changes.text
    assert deleted_changes.json()["data"][0]["summary"] == "Deleted the project"
    assert "Fifth" not in names(list_projects(client, ""))
    kept = client.post(
        "/api/v1/projects", headers=headers, json={"name": "Kept", "status": "active"}
    )
    assert kept.status_code == 201, kept.text
    with httpx.Client(base_url=client.base_url, timeout=15) as other:
        sign_up(other)
        refused = other.get(f"/api/v1/projects/{kept.json()['data']['id']}/changes")
        assert refused.status_code == 404, refused.text
        assert refused.json()["error"]["code"] == "PROJECT_NOT_FOUND"


# forge:feature:test-helper:start
@contextmanager
def joined_member(admin: httpx.Client, admin_csrf: str) -> Iterator[httpx.Client]:
    """A member the admin invites into its organisation, signed in on its own client."""
    invited = credentials()
    token = invite(admin, admin_csrf, invited["email"])
    with httpx.Client(base_url=admin.base_url, timeout=15) as member:
        joined = member.post(
            "/api/v1/auth/accept-invite", json={**invited, "token": token}
        )
        assert joined.status_code == 201, joined.text
        yield member


# forge:feature:test-helper:end


# Every projects route and the permission it needs, as (method, path, permission).
PROJECT_ROUTES = (
    ("GET", "", "view"),
    ("GET", "/export", "view"),
    ("GET", "/{id}", "view"),
    ("GET", "/{id}/changes", "view"),
    ("POST", "", "create"),
    ("PUT", "/{id}", "edit"),
    ("DELETE", "/{id}", "delete"),
    ("POST", "/{id}/restore", "restore"),
)


def call_each_route(client: httpx.Client, project_id: str) -> dict[str, httpx.Response]:
    headers = {"x-csrf-token": client.cookies["starter_csrf"]}
    body = {"name": "Permission check", "status": "active"}
    responses = {}
    for method, path, _ in PROJECT_ROUTES:
        responses[f"{method} {path}"] = client.request(
            method,
            "/api/v1/projects" + path.replace("{id}", project_id),
            headers=headers,
            json=body if method in {"POST", "PUT"} and "restore" not in path else None,
        )
    return responses


def test_each_projects_endpoint_refuses_a_member_without_its_permission(
    client: httpx.Client,
) -> None:
    # Audit: each projects route must check its own permission, so a route that skips the check
    # or names the wrong one lets a member through. The member's permissions come from the API,
    # so the table holds whatever the mapping says. Real HTTP and Postgres; no test seam.
    _, csrf = sign_up(client)
    created = client.post(
        "/api/v1/projects",
        headers={"x-csrf-token": csrf},
        json={"name": "Admin project", "status": "active"},
    )
    assert created.status_code == 201, created.text
    project_id = created.json()["data"]["id"]

    with joined_member(client, csrf) as member:
        me = member.get("/api/v1/auth/me")
        assert me.status_code == 200, me.text
        permissions = me.json()["data"]["permissions"]
        refused = []
        for (method, path, permission), response in zip(
            PROJECT_ROUTES, call_each_route(member, project_id).values(), strict=True
        ):
            if f"projects.{permission}" in permissions:
                assert response.status_code != 403, (method, path, response.text)
            else:
                assert response.status_code == 403, (method, path, response.text)
                assert response.json()["error"]["code"] == "PERMISSION_DENIED"
                refused.append(permission)
        # The starter's mapping lets a member do everything but delete and restore.
        assert refused == ["delete", "restore"]

    for route, response in call_each_route(client, project_id).items():
        assert response.status_code != 403, (route, response.text)


def test_an_admin_restores_a_deleted_project(client: httpx.Client) -> None:
    # Audit: an admin sees deleted projects only when it asks, restores one with a history row,
    # and a member never sees a deleted project. Real HTTP and Postgres; no test seam.
    admin, csrf = sign_up(client)
    headers = {"x-csrf-token": csrf}
    create_projects(
        client, csrf, [("Kept project", "active"), ("Gone project", "active")]
    )
    gone = next(
        item
        for item in list_projects(client, "")["items"]
        if item["name"] == "Gone project"
    )
    path = f"/api/v1/projects/{gone['id']}"
    assert client.delete(path, headers=headers).status_code == 200

    with_deleted = list_projects(client, "deleted=yes&sortBy=name&sortOrder=asc")
    assert names(with_deleted) == ["Gone project", "Kept project"]
    assert with_deleted["paging"]["total"] == 2
    deleted_item = with_deleted["items"][0]
    assert deleted_item["deletedAtUtc"] is not None
    assert deleted_item["deletedByEmail"] == admin["email"]
    assert with_deleted["items"][1]["deletedAtUtc"] is None
    assert names(list_projects(client, "")) == ["Kept project"]
    assert "Gone project" in client.get("/api/v1/projects/export?deleted=yes").text
    assert "Gone project" not in client.get("/api/v1/projects/export").text

    restored = client.post(f"{path}/restore", headers=headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["deletedAtUtc"] is None
    assert restored.json()["data"]["deletedByEmail"] is None
    assert names(list_projects(client, "sortBy=name&sortOrder=asc")) == [
        "Gone project",
        "Kept project",
    ]
    changes = client.get(f"{path}/changes").json()["data"]
    assert [entry["summary"] for entry in changes[:2]] == [
        "Restored the project",
        "Deleted the project",
    ]
    again = client.post(f"{path}/restore", headers=headers)
    assert again.status_code == 404, again.text
    assert again.json()["error"]["code"] == "PROJECT_NOT_FOUND"

    with joined_member(client, csrf) as member:
        assert client.delete(path, headers=headers).status_code == 200
        member_list = list_projects(member, "deleted=yes")
        assert names(member_list) == ["Kept project"]
        assert all(item["deletedAtUtc"] is None for item in member_list["items"])
        hidden = member.get(path)
        assert hidden.status_code == 404, hidden.text
        assert hidden.json()["error"]["code"] == "PROJECT_NOT_FOUND"
    seen = client.get(path)
    assert seen.status_code == 200, seen.text
    assert seen.json()["data"]["deletedAtUtc"] is not None


# forge:feature:mcp:start
MCP_FEATURE = "projects"
MCP_TOOL_PREFIX = "projects"
MCP_SINGULAR = "project"
MCP_ID_FIELD = "project_id"
MCP_SEARCH_FIELD = "query"
MCP_NAME_FIELD = "name"
MCP_BAD_VALUE = ""
MCP_LINKS: dict[str, tuple[str, str]] = {}


def _mcp_payload(
    client: httpx.Client, csrf: str, *, changed: bool = False
) -> dict[str, object]:
    # forge:feature:mcp-input:start
    return {
        "name": f"Agent project {uuid4().hex[:8]}{' changed' if changed else ''}",
        "status": "archived" if changed else "active",
    }
    # forge:feature:mcp-input:end


def _mcp_agent(
    client: httpx.Client, csrf: str, role: str
) -> tuple[dict[str, object], str]:
    from conftest import add_agent_key

    return add_agent_key(client, csrf, f"agent-{uuid4().hex[:8]}", role)


def _mcp_error(result: object) -> dict[str, object]:
    structured = getattr(result, "structured_content")
    assert isinstance(structured, dict)
    error = structured["error"]
    assert isinstance(error, dict)
    return error


def test_an_agent_searches_reads_creates_and_updates_projects_through_mcp_as_its_account(
    client: httpx.Client,
) -> None:
    # Audit: protects tool names, concise and detailed results, and agent attribution through the
    # real MCP transport. REST cases do not call these tools; generated feature tests copy this
    # boundary case with field-based payloads. No production test seam.
    owner, csrf = sign_up(client)
    agent, key = _mcp_agent(client, csrf, "member")

    async def use_tools() -> str:
        from conftest import agent_client

        async with agent_client(key) as session:
            tools = (await session.list_tools()).tools
            project_tools = {
                tool.name
                for tool in tools
                if tool.name.startswith(f"{MCP_TOOL_PREFIX}_")
            }
            assert project_tools == {
                f"{MCP_TOOL_PREFIX}_search",
                f"{MCP_TOOL_PREFIX}_get",
                f"{MCP_TOOL_PREFIX}_create",
                f"{MCP_TOOL_PREFIX}_update",
            }
            valid = _mcp_payload(client, csrf)
            created = await session.call_tool(f"{MCP_TOOL_PREFIX}_create", valid)
            assert created.is_error is False
            assert created.structured_content is not None
            project_id = created.structured_content[MCP_ID_FIELD]
            assert created.structured_content[MCP_NAME_FIELD] == valid[MCP_NAME_FIELD]
            assert created.structured_content.get("status_label")
            assert "created_by_email" not in created.structured_content
            # Linked ids retain their public display names in the concise MCP response.
            for field, (target, label) in MCP_LINKS.items():
                linked_id = valid[field]
                name_field = field.removesuffix("_id") + "_name"
                if linked_id is None:
                    assert created.structured_content[name_field] is None
                else:
                    linked = client.get(f"/api/v1/{target}/{linked_id}")
                    assert linked.status_code == 200, linked.text
                    assert (
                        created.structured_content[name_field]
                        == linked.json()["data"][label]
                    )

            bad = _mcp_payload(client, csrf)
            bad[MCP_NAME_FIELD] = MCP_BAD_VALUE
            invalid = await session.call_tool(f"{MCP_TOOL_PREFIX}_create", bad)
            assert invalid.is_error is True
            invalid_error = _mcp_error(invalid)
            assert invalid_error["kind"] == "invalid_input"
            assert invalid_error["retryable"] is False
            assert MCP_NAME_FIELD in str(invalid_error["details"])
            message = invalid_error["message"]
            assert isinstance(message, str)
            assert "Example:" in message

            fetched = await session.call_tool(
                f"{MCP_TOOL_PREFIX}_get", {MCP_ID_FIELD: project_id}
            )
            assert fetched.is_error is False
            assert fetched.structured_content is not None
            assert fetched.structured_content[MCP_ID_FIELD] == project_id
            assert fetched.structured_content[MCP_NAME_FIELD] == valid[MCP_NAME_FIELD]
            assert fetched.structured_content.get("status_label")
            assert "created_by_email" not in fetched.structured_content

            detailed = await session.call_tool(
                f"{MCP_TOOL_PREFIX}_get",
                {MCP_ID_FIELD: project_id, "response_format": "detailed"},
            )
            assert detailed.structured_content is not None
            assert detailed.structured_content["created_by_email"] == agent["email"]

            found = await session.call_tool(
                f"{MCP_TOOL_PREFIX}_search", {MCP_SEARCH_FIELD: valid[MCP_NAME_FIELD]}
            )
            assert found.is_error is False
            assert found.structured_content is not None
            item = found.structured_content["items"][0]
            assert item[MCP_ID_FIELD] == project_id
            assert item[MCP_NAME_FIELD] == valid[MCP_NAME_FIELD]
            assert item.get("status_label")
            assert "created_by_email" not in item

            full = await session.call_tool(
                f"{MCP_TOOL_PREFIX}_search",
                {
                    MCP_SEARCH_FIELD: valid[MCP_NAME_FIELD],
                    "response_format": "detailed",
                },
            )
            assert full.structured_content is not None
            assert (
                full.structured_content["items"][0]["created_by_email"]
                == agent["email"]
            )

            changed = _mcp_payload(client, csrf, changed=True)
            updated = await session.call_tool(
                f"{MCP_TOOL_PREFIX}_update", {MCP_ID_FIELD: project_id, **changed}
            )
            assert updated.is_error is False
            assert updated.structured_content is not None
            assert updated.structured_content.get("status_label")
            return str(project_id)

    import asyncio

    project_id = asyncio.run(use_tools())
    changes = client.get(f"/api/v1/{MCP_FEATURE}/{project_id}/changes")
    assert changes.status_code == 200, changes.text
    assert [entry["actorEmail"] for entry in changes.json()["data"]] == [
        agent["email"],
        agent["email"],
    ]
    history = client.get("/api/v1/history").json()["data"]
    summaries = [
        entry["summary"] for entry in history if entry["actorEmail"] == agent["email"]
    ]
    assert any(summary.endswith(f"Created the {MCP_SINGULAR}") for summary in summaries)
    assert any(" changed from " in summary for summary in summaries)
    assert owner["email"] not in {
        entry["actorEmail"] for entry in changes.json()["data"]
    }


def test_a_member_agent_cannot_delete_or_restore_a_project_through_mcp(
    client: httpx.Client,
) -> None:
    # Audit: protects role filtering and the call boundary after the switch is enabled. Existing
    # REST permission tests do not prove the tools/list and tools/call policy. No production seam.
    _, csrf = sign_up(client)
    _, key = _mcp_agent(client, csrf, "member")
    with joined_member(client, csrf) as member:
        me = member.get("/api/v1/auth/me")
        assert me.status_code == 200, me.text
        permissions = set(me.json()["data"]["permissions"])
    tool_permissions = {
        "search": "view",
        "get": "view",
        "create": "create",
        "update": "edit",
        "delete": "delete",
        "restore": "restore",
    }
    enabled = client.put(
        f"/api/v1/agent-tools/{MCP_FEATURE}",
        headers={"x-csrf-token": csrf},
        json={"deleteAndRestore": True},
    )
    assert enabled.status_code == 200, enabled.text
    project = client.post(
        f"/api/v1/{MCP_FEATURE}",
        headers={"x-csrf-token": csrf},
        json=_mcp_payload(client, csrf),
    )
    assert project.status_code == 201, project.text
    project_id = project.json()["data"]["id"]

    async def denied() -> None:
        from conftest import agent_client

        async with agent_client(key) as session:
            names = {
                tool.name
                for tool in (await session.list_tools()).tools
                if tool.name.startswith(f"{MCP_TOOL_PREFIX}_")
            }
            assert names == {
                f"{MCP_TOOL_PREFIX}_{action}"
                for action, permission in tool_permissions.items()
                if f"{MCP_FEATURE}.{permission}" in permissions
            }
            for action in ("delete", "restore"):
                if f"{MCP_FEATURE}.{action}" in permissions:
                    continue
                refused = await session.call_tool(
                    f"{MCP_TOOL_PREFIX}_{action}", {MCP_ID_FIELD: project_id}
                )
                assert refused.is_error is True
                error = _mcp_error(refused)
                assert error["kind"] == "not_allowed"
                assert error["retryable"] is False

    import asyncio

    asyncio.run(denied())
    kept = client.get(f"/api/v1/{MCP_FEATURE}/{project_id}")
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["deletedAtUtc"] is None


def test_project_delete_and_restore_tools_stay_off_until_an_admin_turns_them_on(
    client: httpx.Client,
) -> None:
    # Audit: protects the off-by-default switch, role-filtered tool list, idempotent soft delete
    # and restore, and project change history at the running API. REST-only tests miss MCP policy.
    _, csrf = sign_up(client)
    agent, key = _mcp_agent(client, csrf, "admin")

    async def admin_tools() -> str:
        from conftest import agent_client

        async with agent_client(key) as session:
            expected = {
                f"{MCP_TOOL_PREFIX}_search",
                f"{MCP_TOOL_PREFIX}_get",
                f"{MCP_TOOL_PREFIX}_create",
                f"{MCP_TOOL_PREFIX}_update",
            }
            before = {
                tool.name
                for tool in (await session.list_tools()).tools
                if tool.name.startswith(f"{MCP_TOOL_PREFIX}_")
            }
            assert before == expected
            created = await session.call_tool(
                f"{MCP_TOOL_PREFIX}_create", _mcp_payload(client, csrf)
            )
            assert created.is_error is False
            assert created.structured_content is not None
            project_id = created.structured_content[MCP_ID_FIELD]
            refused = await session.call_tool(
                f"{MCP_TOOL_PREFIX}_delete", {MCP_ID_FIELD: project_id}
            )
            assert refused.is_error is True
            error = _mcp_error(refused)
            assert error["kind"] == "not_allowed"
            assert error["retryable"] is False

            enabled = client.put(
                f"/api/v1/agent-tools/{MCP_FEATURE}",
                headers={"x-csrf-token": csrf},
                json={"deleteAndRestore": True},
            )
            assert enabled.status_code == 200, enabled.text
            on = {
                tool.name
                for tool in (await session.list_tools()).tools
                if tool.name.startswith(f"{MCP_TOOL_PREFIX}_")
            }
            assert on == expected | {
                f"{MCP_TOOL_PREFIX}_delete",
                f"{MCP_TOOL_PREFIX}_restore",
            }
            for action in ("delete", "delete", "restore", "restore"):
                result = await session.call_tool(
                    f"{MCP_TOOL_PREFIX}_{action}", {MCP_ID_FIELD: project_id}
                )
                assert result.is_error is False

            disabled = client.put(
                f"/api/v1/agent-tools/{MCP_FEATURE}",
                headers={"x-csrf-token": csrf},
                json={"deleteAndRestore": False},
            )
            assert disabled.status_code == 200, disabled.text
            off = {
                tool.name
                for tool in (await session.list_tools()).tools
                if tool.name.startswith(f"{MCP_TOOL_PREFIX}_")
            }
            assert off == expected
            return str(project_id)

    import asyncio

    project_id = asyncio.run(admin_tools())
    changes = client.get(f"/api/v1/{MCP_FEATURE}/{project_id}/changes")
    assert changes.status_code == 200, changes.text
    actions = [
        entry
        for entry in changes.json()["data"]
        if entry["summary"] in {"Deleted the project", "Restored the project"}
    ]
    assert [(entry["actorEmail"], entry["summary"]) for entry in actions] == [
        (agent["email"], "Restored the project"),
        (agent["email"], "Deleted the project"),
    ]


# forge:feature:mcp:end
