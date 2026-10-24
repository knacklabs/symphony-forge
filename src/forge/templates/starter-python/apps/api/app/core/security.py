import hashlib
import hmac
import threading
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from app.core.config import Settings
from app.core.errors import ApiError, _error_response

_STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_RATE_LIMITED_PATHS = {
    "/api/v1/auth/sign-up",
    "/api/v1/auth/sign-in",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/accept-invite",
    "/api/v1/error-reports",
}
_RATE_LIMIT_SECONDS = 60
_RATE_LIMIT_COUNT = 30
# ponytail: per instance; a shared limit comes with Redis
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMITS: dict[tuple[str, str], list[float]] = {}


def _headers(correlation_id: str, script_nonce: str | None = None) -> dict[str, str]:
    headers = {
        "X-Correlation-Id": correlation_id,
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Origin-Agent-Cluster": "?1",
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
        "X-DNS-Prefetch-Control": "off",
        "X-Download-Options": "noopen",
        "X-Frame-Options": "SAMEORIGIN",
        "X-Permitted-Cross-Domain-Policies": "none",
        "X-XSS-Protection": "0",
        "Content-Security-Policy": (
            "default-src 'self';base-uri 'self';font-src 'self' https: data:;form-action 'self';"
            "frame-ancestors 'self';img-src 'self' data:;object-src 'none';script-src 'self'"
            + (
                f" https://cdn.jsdelivr.net 'nonce-{script_nonce}'"
                if script_nonce
                else ""
            )
            + ";script-src-attr 'none';style-src 'self' https: 'unsafe-inline';upgrade-insecure-requests"
        ),
    }
    headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


def _is_rate_limited(client: str, path: str) -> bool:
    now = time.monotonic()
    key = (client, path)
    with _RATE_LIMIT_LOCK:
        attempts = [
            stamp
            for stamp in _RATE_LIMITS.get(key, [])
            if now - stamp < _RATE_LIMIT_SECONDS
        ]
        if len(attempts) >= _RATE_LIMIT_COUNT:
            _RATE_LIMITS[key] = attempts
            return True
        attempts.append(now)
        _RATE_LIMITS[key] = attempts
    return False


def verify_csrf(request: Request) -> None:
    cookie_token = request.cookies.get("starter_csrf")
    header_token = request.headers.get("x-csrf-token")
    expected_hash = getattr(request.state, "csrf_token_hash", None)
    if (
        not cookie_token
        or not header_token
        or not expected_hash
        or not hmac.compare_digest(cookie_token, header_token)
        or not hmac.compare_digest(
            hashlib.sha256(header_token.encode()).hexdigest(), expected_hash
        )
    ):
        raise ApiError(403, "CSRF_CHECK_FAILED", "Refresh the page and try again.")


def install_security_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = request.headers.get("x-correlation-id", "")
        correlation_id = incoming if incoming and len(incoming) <= 128 else str(uuid4())
        request.state.correlation_id = correlation_id
        settings: Settings | None = getattr(request.app.state, "settings", None)
        origin = request.headers.get("origin")

        response: Response
        if request.method == "OPTIONS":
            response = Response(status_code=204)
        elif (
            request.method in _STATE_CHANGING_METHODS
            and origin
            and settings is not None
            and origin != settings.app_origin
        ):
            response = JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "CSRF_CHECK_FAILED",
                        "message": "Refresh the page and try again.",
                        "details": None,
                        "errorId": str(uuid4()),
                    },
                },
            )
        elif (
            request.url.path in _RATE_LIMITED_PATHS
            and request.client
            and _is_rate_limited(request.client.host, request.url.path)
        ):
            response = JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Wait and try again.",
                        "details": None,
                        "errorId": str(uuid4()),
                    },
                },
            )
        else:
            try:
                response = await call_next(request)
            # Keep database driver details out of server logs.
            except Exception as error:  # noqa: BLE001
                response = _error_response(
                    request,
                    500,
                    "INTERNAL_SERVER_ERROR",
                    "Something went wrong. Try again.",
                    None,
                    exception=error,
                )

        nonce = (
            getattr(request.state, "script_nonce", None)
            if request.url.path == "/api/docs"
            else None
        )
        response.headers.update(_headers(correlation_id, nonce))
        if settings is not None and origin == settings.app_origin:
            response.headers["Access-Control-Allow-Origin"] = settings.app_origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, X-CSRF-Token, X-Correlation-Id"
            )
            response.headers["Vary"] = "Origin"
        return response
