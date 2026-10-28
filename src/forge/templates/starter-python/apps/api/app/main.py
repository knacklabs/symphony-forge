import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse
from starlette.routing import Route

from app.auth import router as auth_router
from app.core import (
    HealthResponse,
    SuccessEnvelope,
    create_database,
    error_report_router,
    install_error_handlers,
    install_security_middleware,
    load_settings,
)
from app.history import router as history_router
from app.mcp import McpEndpoint, create_session_manager
from app.organisations import router as organisations_router
from app.projects import router as projects_router


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    engine, session_factory = create_database(settings.database_url)
    application.state.settings = settings
    application.state.session_factory = session_factory
    try:
        manager = create_session_manager()
        application.state.mcp_manager = manager
        async with manager.run():
            yield
    finally:
        engine.dispose()


app = FastAPI(
    title="Starter API",
    description="Account sign-in and project management API.",
    version="1.0.0",
    docs_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(organisations_router)
app.include_router(history_router)
app.include_router(error_report_router)
install_error_handlers(app)
install_security_middleware(app)
app.router.routes.append(Route("/mcp", endpoint=McpEndpoint()))
app.router.routes.append(Route("/mcp/", endpoint=McpEndpoint()))


@app.get("/api/docs", include_in_schema=False)
def swagger_docs(request: Request) -> HTMLResponse:
    nonce = secrets.token_urlsafe(18)
    page = get_swagger_ui_html(
        openapi_url=app.openapi_url or "", title=f"{app.title} - Swagger UI"
    )
    html = (
        bytes(page.body)
        .decode("utf-8")
        .replace("<script>", f'<script nonce="{nonce}">')
    )
    request.state.script_nonce = nonce
    return HTMLResponse(html)


@app.get(
    "/health",
    response_model=SuccessEnvelope[HealthResponse],
    summary="Check whether the API is ready.",
)
def health() -> SuccessEnvelope[HealthResponse]:
    return SuccessEnvelope(data=HealthResponse(status="ok"))


@app.get("/{path:path}", include_in_schema=False)
def web_app(request: Request, path: str) -> FileResponse:
    web_root = Path(__file__).resolve().parents[3] / "apps" / "web" / "dist"
    requested = (web_root / path).resolve()
    if requested.is_relative_to(web_root.resolve()) and requested.is_file():
        return FileResponse(requested)
    accept = request.headers.get("accept", "")
    accepts_html = not accept
    for accepted in accept.split(","):
        media_type, *parameters = accepted.strip().split(";")
        quality = next(
            (
                parameter.split("=", 1)[1]
                for parameter in parameters
                if parameter.strip().startswith("q=")
            ),
            "1",
        )
        if media_type in {"text/html", "text/*", "*/*"} and quality != "0":
            accepts_html = True
    if (
        accepts_html
        and not path.startswith(("api/", "health/", "mcp/"))
        and path not in {"api", "health", "mcp"}
    ):
        return FileResponse(web_root / "index.html")
    raise HTTPException(status_code=404)
