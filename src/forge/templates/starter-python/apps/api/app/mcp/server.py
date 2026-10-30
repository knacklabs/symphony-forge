import hashlib
import re
import tomllib
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from fastapi import Request
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    GetPromptRequestParams,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    ListToolsResult,
    PaginatedRequestParams,
    ReadResourceRequestParams,
    ReadResourceResult,
)
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.core import (
    ToolContext,
    ToolError,
    call_tool,
    create_once,
    get_prompt,
    list_prompts,
    list_resource_templates,
    list_resources,
    list_tools,
    rate_limit_retry_after,
    read_resource,
    report_error,
    tool_failure,
)
from app.organisations import AgentAccess, agent_for_key

CALLS_PER_MINUTE = 120


def _context(request: Request) -> ToolContext:
    access = cast(AgentAccess, request.state.agent_access)

    def report(error: Exception) -> None:
        report_error(
            request,
            source="api",
            name=type(error).__name__,
            path="/mcp",
            error_id=uuid4(),
            method=request.method,
            status=500,
        )

    return ToolContext(
        account=access.principal,
        delete_and_restore=access.delete_and_restore,
        session_factory=cast(sessionmaker[Session], request.app.state.session_factory),
        create_once=create_once,
        report_error=report,
    )


def create_session_manager() -> StreamableHTTPSessionManager:
    manifest = Path(__file__).resolve().parents[2] / "pyproject.toml"
    name = tomllib.loads(manifest.read_text("utf-8"))["project"]["name"]

    async def tools(
        context: ServerRequestContext[Any], params: PaginatedRequestParams | None
    ) -> ListToolsResult:
        request = cast(Request, context.request)
        return ListToolsResult(tools=list_tools(_context(request)))

    async def call(
        context: ServerRequestContext[Any], params: CallToolRequestParams
    ) -> CallToolResult:
        request = cast(Request, context.request)
        retry_after = rate_limit_retry_after(
            cast(str, request.state.agent_key_hash), "/mcp", limit=CALLS_PER_MINUTE
        )
        if retry_after:
            return tool_failure(
                ToolError(
                    "rate_limited",
                    f"This agent key made {CALLS_PER_MINUTE} calls in the last minute. Wait {retry_after} seconds and try again.",
                    retryable=True,
                    retry_after_seconds=retry_after,
                )
            )
        return await call_tool(params.name, params.arguments or {}, _context(request))

    async def resources(
        context: ServerRequestContext[Any], params: PaginatedRequestParams | None
    ) -> ListResourcesResult:
        return ListResourcesResult(
            resources=list_resources(_context(cast(Request, context.request)))
        )

    async def templates(
        context: ServerRequestContext[Any], params: PaginatedRequestParams | None
    ) -> ListResourceTemplatesResult:
        return ListResourceTemplatesResult(
            resource_templates=list_resource_templates(
                _context(cast(Request, context.request))
            )
        )

    async def read(
        context: ServerRequestContext[Any], params: ReadResourceRequestParams
    ) -> ReadResourceResult:
        return await read_resource(
            str(params.uri), _context(cast(Request, context.request))
        )

    async def prompts(
        context: ServerRequestContext[Any], params: PaginatedRequestParams | None
    ) -> ListPromptsResult:
        return ListPromptsResult(
            prompts=list_prompts(_context(cast(Request, context.request)))
        )

    async def prompt(
        context: ServerRequestContext[Any], params: GetPromptRequestParams
    ) -> GetPromptResult:
        return get_prompt(
            params.name,
            params.arguments or {},
            _context(cast(Request, context.request)),
        )

    server: Server[Any] = Server(
        name,
        version="1.0.0",
        on_list_tools=tools,
        on_call_tool=call,
        on_list_resources=resources,
        on_list_resource_templates=templates,
        on_read_resource=read,
        on_list_prompts=prompts,
        on_get_prompt=prompt,
    )
    return StreamableHTTPSessionManager(server, stateless=True, json_response=True)


class McpEndpoint:
    """Authenticate before the MCP transport reads the request body."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive)
        match = re.fullmatch(
            r"Bearer ([^\s]+)", request.headers.get("authorization", ""), re.IGNORECASE
        )
        key_hash = hashlib.sha256(match[1].encode()).hexdigest() if match else None

        def authenticate() -> AgentAccess | None:
            if key_hash is None:
                return None
            factory = cast(sessionmaker[Session], request.app.state.session_factory)
            with factory() as db:
                return agent_for_key(db, key_hash)

        access = await run_in_threadpool(authenticate)
        if access is None:
            response = JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "UNAUTHENTICATED",
                        "message": "Send a valid agent key.",
                        "details": None,
                        "errorId": str(uuid4()),
                    },
                },
            )
            await response(scope, receive, send)
            return
        request.state.agent_access = access
        request.state.agent_key_hash = key_hash
        manager = cast(StreamableHTTPSessionManager, request.app.state.mcp_manager)
        await manager.handle_request(scope, receive, send)
