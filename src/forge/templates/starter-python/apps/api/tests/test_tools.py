"""Tool registry contracts that do not need the API or database."""

import asyncio
import threading
from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

import pytest
from mcp.shared.exceptions import MCPError
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel

from app.core import (
    AccountPrincipal,
    ToolContext,
    ToolResult,
    call_tool,
    define_feature_tools,
    define_permissions,
    define_prompt,
    define_tool,
    get_prompt,
    list_prompts,
    list_resource_templates,
    list_resources,
    list_tools,
    read_resource,
)


@pytest.fixture(scope="module", autouse=True)
def isolated_api() -> Iterator[None]:
    # These cases only exercise the in-memory MCP registries and call boundary.
    yield


class _WidgetInput(BaseModel):
    name: str


class _Widget(BaseModel):
    id: UUID
    name: str
    updated_at_utc: datetime


class _WidgetPaging(BaseModel):
    total: int
    total_capped: bool
    next_cursor: str | None


class _WidgetPage(BaseModel):
    items: Sequence[_Widget]
    paging: _WidgetPaging


class _WidgetQuery(BaseModel):
    search: str | None = None
    deleted: Literal["yes"] | None = None
    limit: int = 20
    sort_by: Literal["name", "updated_at_utc"] = "updated_at_utc"
    sort_order: Literal["asc", "desc"] = "desc"
    after: str | None = None
    before: str | None = None


class _WidgetService:
    def __init__(self, db: object) -> None:
        self.db = db

    def list(self, account: AccountPrincipal, query: _WidgetQuery) -> _WidgetPage:
        raise NotImplementedError

    def get(self, account: AccountPrincipal, item_id: UUID) -> _Widget:
        raise NotImplementedError

    def create(self, account: AccountPrincipal, input_data: _WidgetInput) -> _Widget:
        raise NotImplementedError

    def update(
        self, account: AccountPrincipal, item_id: UUID, input_data: _WidgetInput
    ) -> _Widget:
        raise NotImplementedError

    def delete(self, account: AccountPrincipal, item_id: UUID) -> None:
        raise NotImplementedError

    def restore(self, account: AccountPrincipal, item_id: UUID) -> _Widget:
        raise NotImplementedError


def test_a_tools_file_can_hide_a_default_tool_and_add_its_own() -> None:
    # Audit: protects the feature extension contract: hidden defaults disappear, custom tools
    # retain their permission, and duplicate names fail. No integration case owns registry rules;
    # generated feature behavior is tested separately through MCP. No production seam.
    feature = f"tool-test-{uuid4().hex[:8]}"
    permissions = define_permissions(
        feature,
        {
            "admin": ["view", "create", "edit", "delete", "restore"],
            "member": ["view", "create", "edit"],
        },
    )
    define_feature_tools(
        feature=feature,
        one="widget",
        permissions=permissions,
        input_model=_WidgetInput,
        output_model=_Widget,
        query_model=_WidgetQuery,
        concise=("name",),
        links={},
        service=_WidgetService,
        api=feature,
        label="name",
        hide=("delete",),
    )

    class _CustomInput(BaseModel):
        value: str

    class _CustomOutput(BaseModel):
        value: str

    custom_name = feature.replace("-", "_") + "_describe"

    def custom_call(
        account: AccountPrincipal, parsed: _CustomInput, context: ToolContext
    ) -> ToolResult:
        return ToolResult(data={"value": parsed.value}, summary="Read one value.")

    def register_custom_tool() -> None:
        define_tool(
            name=custom_name,
            permission=permissions.delete,
            description="Read a widget note. Use this for a custom lookup.",
            input_model=_CustomInput,
            output_model=_CustomOutput,
            annotations=ToolAnnotations(
                title="Describe a widget",
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=False,
                open_world_hint=False,
            ),
            call=custom_call,
            feature=feature,
        )

    register_custom_tool()
    with pytest.raises(ValueError, match="Duplicate tool"):
        register_custom_tool()

    account = AccountPrincipal(uuid4(), "admin@example.test", uuid4(), "admin")
    names = {
        tool.name
        for tool in list_tools(
            ToolContext(account=account, delete_and_restore=(feature,))
        )
        if tool.name.startswith(feature.replace("-", "_") + "_")
    }
    assert f"{feature.replace('-', '_')}_delete" not in names
    assert f"{feature.replace('-', '_')}_restore" in names
    assert custom_name in names
    admin_result = asyncio.run(
        call_tool(custom_name, {"value": "visible"}, ToolContext(account=account))
    )
    assert admin_result.is_error is False
    assert admin_result.structured_content is not None
    assert admin_result.structured_content["value"] == "visible"
    member = AccountPrincipal(uuid4(), "member@example.test", uuid4(), "member")
    member_names = {
        tool.name
        for tool in list_tools(
            ToolContext(account=member, delete_and_restore=(feature,))
        )
        if tool.name.startswith(feature.replace("-", "_") + "_")
    }
    assert custom_name not in member_names
    assert f"{feature.replace('-', '_')}_delete" not in member_names
    member_result = asyncio.run(
        call_tool(custom_name, {"value": "hidden"}, ToolContext(account=member))
    )
    assert member_result.is_error is True
    assert member_result.structured_content is not None
    assert member_result.structured_content["error"]["kind"] == "not_allowed"


def test_a_tool_over_its_time_limit_gets_a_retryable_unavailable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Audit: protects the deadline contract at call_tool, which HTTP tests cannot make slow
    # without an external delay. The callback is an isolated pure function; the named timeout
    # constant is the one allowed test setting, and no network or database is involved.
    import app.core.tools as tools_module

    feature = f"timeout-{uuid4().hex[:8]}"
    permissions = define_permissions(
        feature,
        {
            "admin": ["view"],
            "member": ["view"],
        },
    )

    class _SlowInput(BaseModel):
        value: str

    class _SlowOutput(BaseModel):
        value: str

    release = threading.Event()

    def slow_call(
        account: AccountPrincipal, parsed: _SlowInput, context: ToolContext
    ) -> ToolResult:
        release.wait()
        return ToolResult(data={"value": parsed.value}, summary="Finished.")

    name = feature + "_slow"
    define_tool(
        name=name,
        permission=permissions.view,
        description="Wait for one slow result. Use this when measuring the call limit.",
        input_model=_SlowInput,
        output_model=_SlowOutput,
        annotations=ToolAnnotations(
            title="Wait for a result",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        ),
        call=slow_call,
        feature=feature,
    )
    monkeypatch.setattr(tools_module, "CALL_LIMIT_SECONDS", 0.01)
    account = AccountPrincipal(uuid4(), "agent@example.test", uuid4(), "admin")

    async def call_before_releasing_worker() -> CallToolResult:
        try:
            result = await asyncio.wait_for(
                call_tool(name, {"value": "wait"}, ToolContext(account=account)),
                timeout=1,
            )
            assert not release.is_set()
            return result
        finally:
            release.set()

    result = asyncio.run(call_before_releasing_worker())
    assert result.is_error is True
    assert result.structured_content is not None
    error = result.structured_content["error"]
    assert error["kind"] == "unavailable"
    assert error["retryable"] is True
    assert error["retry_after_seconds"] == 5


def test_a_resource_read_without_the_view_permission_is_refused() -> None:
    # Audit: protects resource discovery and reads when a role lacks view permission. Tool
    # permission coverage does not exercise the resource registry. This pure registry case needs
    # no API or database seam.
    feature = f"hidden_{uuid4().hex[:8]}"
    permissions = define_permissions(feature, {"admin": ["view"], "member": []})
    define_feature_tools(
        feature=feature,
        one="widget",
        permissions=permissions,
        input_model=_WidgetInput,
        output_model=_Widget,
        query_model=_WidgetQuery,
        concise=("name",),
        links={},
        service=_WidgetService,
        api=feature,
        label="name",
    )
    admin = AccountPrincipal(uuid4(), "admin@example.test", uuid4(), "admin")
    member = AccountPrincipal(uuid4(), "member@example.test", uuid4(), "member")
    admin_context = ToolContext(account=admin)
    member_context = ToolContext(account=member)
    fields_uri = f"app://{feature}/fields"
    item_template = f"app://{feature}/{{widget_id}}"

    assert any(
        str(resource.uri) == fields_uri for resource in list_resources(admin_context)
    )
    assert any(
        template.uri_template == item_template
        for template in list_resource_templates(admin_context)
    )
    assert all(
        not str(resource.uri).startswith(f"app://{feature}/")
        for resource in list_resources(member_context)
    )
    assert all(
        not template.uri_template.startswith(f"app://{feature}/")
        for template in list_resource_templates(member_context)
    )

    async def read_denied_resource() -> None:
        with pytest.raises(MCPError) as denied:
            await read_resource(fields_uri, member_context)
        assert denied.value.code == -32002
        assert isinstance(denied.value.data, dict)
        assert denied.value.data["kind"] == "not_allowed"
        assert denied.value.data["retryable"] is False
        assert "view" in denied.value.data["message"].casefold()

    asyncio.run(read_denied_resource())


def test_a_tools_file_can_add_a_prompt_with_its_inputs() -> None:
    # Audit: protects prompt role visibility, input requirements, rendered content, and duplicate
    # rejection. No starter prompt exists to cover this registry contract; no production seam.
    feature = f"prompt_{uuid4().hex[:8]}"
    permissions = define_permissions(feature, {"admin": ["view"], "member": []})

    class _ReviewPromptInput(BaseModel):
        project_name: str
        status: str | None = None

    def render_review(args: _ReviewPromptInput) -> str:
        return f"Review {args.project_name} in {args.status or 'the default'} mode."

    prompt_name = f"{feature}_review"
    define_prompt(
        name=prompt_name,
        description="Prepare a project review request for an agent.",
        permission=permissions.view,
        arguments=_ReviewPromptInput,
        render=render_review,
    )
    admin = AccountPrincipal(uuid4(), "admin@example.test", uuid4(), "admin")
    member = AccountPrincipal(uuid4(), "member@example.test", uuid4(), "member")
    admin_context = ToolContext(account=admin)
    member_context = ToolContext(account=member)

    prompt = next(
        entry for entry in list_prompts(admin_context) if entry.name == prompt_name
    )
    prompt_arguments = prompt.arguments
    assert prompt_arguments is not None
    arguments = {argument.name: argument for argument in prompt_arguments}
    assert set(arguments) == {"project_name", "status"}
    assert arguments["project_name"].required is True
    assert arguments["status"].required is False
    assert {name for name, argument in arguments.items() if argument.required} == {
        "project_name"
    }
    assert all(entry.name != prompt_name for entry in list_prompts(member_context))

    result = get_prompt(
        prompt_name,
        {"project_name": "Atlas", "status": "archived"},
        admin_context,
    )
    assert len(result.messages) == 1
    message = result.messages[0]
    assert message.role == "user"
    assert isinstance(message.content, TextContent)
    assert message.content.text == "Review Atlas in archived mode."
    omitted_optional = get_prompt(prompt_name, {"project_name": "Atlas"}, admin_context)
    assert len(omitted_optional.messages) == 1
    optional_message = omitted_optional.messages[0]
    assert isinstance(optional_message.content, TextContent)
    assert optional_message.content.text == "Review Atlas in the default mode."

    with pytest.raises(MCPError, match="role cannot use this prompt"):
        get_prompt(
            prompt_name,
            {"project_name": "Atlas", "status": "archived"},
            member_context,
        )

    with pytest.raises(MCPError):
        get_prompt(prompt_name, {}, admin_context)
    with pytest.raises(MCPError):
        get_prompt(
            prompt_name,
            {"project_name": "Atlas", "unexpected": True},
            admin_context,
        )
    with pytest.raises(ValueError, match="Duplicate prompt"):
        define_prompt(
            name=prompt_name,
            description="A duplicate prompt.",
            permission=permissions.view,
            arguments=_ReviewPromptInput,
            render=render_review,
        )
