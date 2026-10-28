"""The agent MCP endpoint and tool contract through the running API."""

import asyncio
from uuid import uuid4

import httpx
from conftest import add_agent_key, agent_client
from mcp.types import CallToolResult, TextContent
from test_api import sign_up


def _agent(
    client: httpx.Client, csrf: str, role: str = "admin"
) -> tuple[dict[str, object], str]:
    return add_agent_key(client, csrf, f"mcp-{uuid4().hex[:8]}", role)


def _mcp_error(result: CallToolResult) -> dict[str, object]:
    structured = result.structured_content
    assert isinstance(structured, dict)
    error = structured["error"]
    assert isinstance(error, dict)
    return error


def _tool_text(result: CallToolResult) -> str:
    content = result.content
    assert content and isinstance(content[0], TextContent)
    return content[0].text


def test_the_mcp_server_refuses_a_missing_or_revoked_agent_key(
    client: httpx.Client,
) -> None:
    # Audit: protects the real /mcp authorization boundary for missing, unknown, valid and
    # revoked keys. The tool calls cannot catch an auth middleware bypass, and unit tests cannot
    # exercise the API transport. This uses the official MCP client for the valid key; no seam.
    _, csrf = sign_up(client)

    def initialize(headers: dict[str, str] | None = None) -> httpx.Response:
        return client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )

    for response in (
        initialize(),
        initialize({"Authorization": "Bearer unknown-agent-key"}),
    ):
        assert response.status_code == 401, response.text
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"
        assert response.headers["WWW-Authenticate"].startswith("Bearer")

    agent, key = _agent(client, csrf)

    async def listed_tools() -> None:
        async with agent_client(key) as session:
            result = await session.list_tools()
            assert any(tool.name == "projects_search" for tool in result.tools)

    asyncio.run(listed_tools())
    revoked = client.delete(
        f"/api/v1/members/{agent['accountId']}/key",
        headers={"x-csrf-token": csrf},
    )
    assert revoked.status_code == 200, revoked.text
    response = initialize({"Authorization": f"Bearer {key}"})
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.headers["WWW-Authenticate"].startswith("Bearer")


def test_every_tool_has_a_description_annotations_schemas_and_the_error_shape(
    client: httpx.Client,
) -> None:
    # Audit: protects each tool as an MCP client sees it, including strict schemas and errors.
    # REST tests cannot catch malformed tools/list or tools/call responses; one list-driven case
    # covers generated and hand-written tools at their shared boundary. No production seam.
    _, csrf = sign_up(client)
    _, key = _agent(client, csrf)

    async def check_tools() -> None:
        async with agent_client(key) as session:
            first_list = (await session.list_tools()).tools
            features = {
                tool.name.removesuffix("_search")
                for tool in first_list
                if tool.name.endswith("_search")
            }
            assert features
            for feature in features:
                access = client.put(
                    f"/api/v1/agent-tools/{feature.replace('_', '-')}",
                    headers={"x-csrf-token": csrf},
                    json={"deleteAndRestore": True},
                )
                assert access.status_code == 200, access.text
            tools = (await session.list_tools()).tools
            for tool in tools:
                assert tool.description and tool.description.count(".") >= 2
                assert tool.annotations is not None
                assert tool.annotations.title
                hints = (
                    tool.annotations.read_only_hint,
                    tool.annotations.destructive_hint,
                    tool.annotations.idempotent_hint,
                    tool.annotations.open_world_hint,
                )
                assert all(isinstance(value, bool) for value in hints)
                generated_feature = next(
                    (
                        feature
                        for feature in features
                        if tool.name.startswith(f"{feature}_")
                    ),
                    None,
                )
                if generated_feature is not None:
                    action = tool.name.removeprefix(f"{generated_feature}_")
                    if action in {
                        "search",
                        "get",
                        "create",
                        "update",
                        "delete",
                        "restore",
                    }:
                        assert tool.annotations.read_only_hint is (
                            action in {"search", "get"}
                        )
                        assert tool.annotations.destructive_hint is (action == "delete")
                        assert tool.annotations.idempotent_hint is (
                            action in {"update", "delete", "restore"}
                        )
                        assert tool.annotations.open_world_hint is False
                    if generated_feature == "projects" and action in {
                        "get",
                        "update",
                        "delete",
                        "restore",
                    }:
                        assert "project_id" in tool.input_schema["properties"]
                        assert "id" not in tool.input_schema["properties"]
                    if action == "search":
                        assert "query" in tool.input_schema["properties"]
                assert tool.input_schema["type"] == "object"
                assert tool.input_schema["additionalProperties"] is False
                assert tool.output_schema is not None
                assert tool.output_schema["type"] == "object"
                result = await session.call_tool(tool.name, {"unknown_argument": True})
                assert result.is_error is True
                error = _mcp_error(result)
                assert error["kind"] == "invalid_input"
                assert error["retryable"] is False
                assert isinstance(error["message"], str) and error["message"]
                assert _tool_text(result)

    asyncio.run(check_tools())


def test_project_search_pages_with_a_cursor_and_says_how_many_match(
    client: httpx.Client,
) -> None:
    # Audit: protects the MCP search page and its guidance through the transport and database.
    # REST paging does not exercise tool cursors or summaries. Data is created through HTTP; no seam.
    _, csrf = sign_up(client)
    _, key = _agent(client, csrf, "member")
    prefix = f"MCP page {uuid4().hex[:8]}"
    for index in range(25):
        created = client.post(
            "/api/v1/projects",
            headers={"x-csrf-token": csrf},
            json={"name": f"{prefix} {index:02d}", "status": "active"},
        )
        assert created.status_code == 201, created.text

    async def check_pages() -> None:
        async with agent_client(key) as session:
            first = await session.call_tool(
                "projects_search",
                {"query": prefix, "sort_by": "name", "sort_order": "asc"},
            )
            assert first.is_error is False
            data = first.structured_content
            assert data is not None
            assert len(data["items"]) == 20
            assert data["total"] == 25
            assert data["next_cursor"]
            summary = _tool_text(first)
            assert "25" in summary
            assert "narrow" in summary.lower()
            second = await session.call_tool(
                "projects_search",
                {
                    "query": prefix,
                    "sort_by": "name",
                    "sort_order": "asc",
                    "cursor": data["next_cursor"],
                },
            )
            assert second.is_error is False
            next_data = second.structured_content
            assert next_data is not None
            assert len(next_data["items"]) == 5
            assert next_data["total"] == 25
            assert next_data["next_cursor"] is None
            invalid = await session.call_tool("projects_search", {"limit": 101})
            assert invalid.is_error is True
            assert _mcp_error(invalid)["kind"] == "invalid_input"

    asyncio.run(check_pages())


def test_a_retried_project_create_with_the_same_idempotency_key_makes_one_project(
    client: httpx.Client,
) -> None:
    # Audit: protects the retry contract at the MCP/database boundary. Existing REST create tests
    # have no idempotency key, so they cannot catch duplicate rows on a replay. No production seam.
    _, csrf = sign_up(client)
    _, key = _agent(client, csrf, "member")
    name = f"MCP retry {uuid4().hex[:8]}"

    async def create_twice() -> None:
        async with agent_client(key) as session:
            args = {
                "name": name,
                "status": "active",
                "idempotency_key": f"retry-{uuid4().hex}",
            }
            first = await session.call_tool("projects_create", args)
            second = await session.call_tool("projects_create", args)
            assert first.is_error is False and second.is_error is False
            assert first.structured_content is not None
            assert second.structured_content is not None
            assert (
                first.structured_content["project_id"]
                == second.structured_content["project_id"]
            )
            search = await session.call_tool("projects_search", {"query": name})
            assert search.structured_content is not None
            assert search.structured_content["total"] == 1

    asyncio.run(create_twice())


def test_a_repeated_project_update_changes_nothing(client: httpx.Client) -> None:
    # Audit: protects idempotent updates and the matching actor history row at the running API.
    # REST update coverage does not call the tool twice as an agent. No production seam.
    _, csrf = sign_up(client)
    agent, key = _agent(client, csrf)
    name = f"MCP update {uuid4().hex[:8]}"

    async def update_twice() -> None:
        async with agent_client(key) as session:
            created = await session.call_tool(
                "projects_create", {"name": name, "status": "active"}
            )
            assert created.is_error is False
            assert created.structured_content is not None
            project_id = created.structured_content["project_id"]
            args = {
                "project_id": project_id,
                "name": f"{name} updated",
                "status": "archived",
            }
            first = await session.call_tool("projects_update", args)
            second = await session.call_tool("projects_update", args)
            assert first.is_error is False and second.is_error is False
            assert first.structured_content is not None
            assert second.structured_content is not None
            assert (
                first.structured_content["updated_at_utc"]
                == second.structured_content["updated_at_utc"]
            )

    asyncio.run(update_twice())
    project = client.get(f"/api/v1/projects?search={name}%20updated").json()["data"][
        "items"
    ][0]
    changes = client.get(f"/api/v1/projects/{project['id']}/changes").json()["data"]
    updates = [
        entry for entry in changes if entry["summary"].startswith("Name changed")
    ]
    assert len(updates) == 1
    assert updates[0]["actorEmail"] == agent["email"]


def test_an_invalid_project_input_gets_a_non_retryable_error_with_an_example(
    client: httpx.Client,
) -> None:
    # Audit: protects plain, repairable validation errors at tools/call. REST validation does not
    # prove the MCP error shape or example. The invalid value is sent through the real transport.
    _, csrf = sign_up(client)
    _, key = _agent(client, csrf, "member")

    async def call_invalid() -> None:
        async with agent_client(key) as session:
            invalid_inputs = (
                (
                    {"name": f"Invalid MCP {uuid4().hex[:8]}", "status": "blocked"},
                    "status",
                ),
                ({"name": "   ", "status": "active"}, "name"),
            )
            for args, field in invalid_inputs:
                result = await session.call_tool("projects_create", args)
                assert result.is_error is True
                error = _mcp_error(result)
                assert error["kind"] == "invalid_input"
                assert error["retryable"] is False
                assert field in str(error["details"])
                message = error["message"]
                assert isinstance(message, str)
                assert "Example:" in message

    asyncio.run(call_invalid())


def test_an_agent_key_over_its_rate_limit_gets_a_retryable_error(
    client: httpx.Client,
) -> None:
    # Audit: protects per-key throttling and confirms another agent remains usable. No other test
    # exercises the API's MCP rate-limit boundary; the loop makes real calls on a newly issued key.
    _, csrf = sign_up(client)
    _, first_key = _agent(client, csrf, "member")
    _, second_key = _agent(client, csrf, "member")

    async def exceed_limit() -> None:
        async with agent_client(first_key) as session:
            last = None
            for index in range(121):
                last = await session.call_tool("projects_search", {"query": ""})
                if index < 120:
                    assert last.is_error is False
                else:
                    assert last.is_error is True
                    error = _mcp_error(last)
                    assert error["kind"] == "rate_limited"
                    assert error["retryable"] is True
                    retry_after = error["retry_after_seconds"]
                    assert isinstance(retry_after, int)
                    assert 1 <= retry_after <= 60
        async with agent_client(second_key) as session:
            result = await session.call_tool("projects_search", {"query": ""})
            assert result.is_error is False

    asyncio.run(exceed_limit())
