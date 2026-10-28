from collections.abc import Mapping
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_report import report_error
from app.core.logging import log_event


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Mapping[str, object] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Mapping[str, object] | None,
    exception: Exception | None = None,
) -> JSONResponse:
    error_id = uuid4()
    if status_code >= 500:
        report_error(
            request,
            source="api",
            name=type(exception).__name__ if exception is not None else "Exception",
            path=request.url.path,
            error_id=error_id,
            method=request.method,
            status=status_code,
        )
    else:
        log_event(
            request,
            "debug",
            "API request rejected",
            "app.core.errors",
            {
                "errorId": str(error_id),
                "status": status_code,
                "method": request.method,
                "path": request.url.path,
            },
        )
    error: dict[str, object] = {
        "code": code,
        "message": "Something went wrong. Try again."
        if status_code >= 500
        else message,
        "details": details if status_code < 500 else None,
        "errorId": str(error_id),
    }
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "data": None, "error": error},
    )


def _validation_fields(errors: list[dict[str, object]]) -> list[dict[str, str]]:
    field_errors: list[dict[str, str]] = []
    for error in errors:
        location = error.get("loc", ())
        if isinstance(location, tuple):
            parts = [
                str(part)
                for part in location
                if part not in {"body", "query", "path", "header", "cookie"}
            ]
        else:
            parts = []
        field = ".".join(parts) or "body"
        error_type = error.get("type")
        reason = (
            "Remove this field."
            if error_type == "extra_forbidden"
            else str(error.get("msg", "Check this field."))
        )
        field_errors.append({"field": field, "reason": reason})
    return field_errors


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, error: ApiError) -> JSONResponse:
        return _error_response(
            request,
            error.status_code,
            error.code,
            error.message,
            error.details,
            exception=error,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        fields = _validation_fields(list(error.errors()))
        return _error_response(
            request,
            400,
            "VALIDATION_ERROR",
            "Check the fields and try again.",
            {"fieldErrors": fields},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        values = {
            400: ("BAD_REQUEST", "Check the request and try again."),
            401: ("UNAUTHENTICATED", "Sign in to continue."),
            403: ("FORBIDDEN", "You do not have permission to do that."),
            404: ("NOT_FOUND", "The requested item was not found."),
            405: ("METHOD_NOT_ALLOWED", "Use a supported request method."),
            409: ("CONFLICT", "That change conflicts with existing data."),
            429: ("RATE_LIMITED", "Too many requests. Wait and try again."),
        }
        code, message = values.get(
            error.status_code,
            ("INTERNAL_SERVER_ERROR", "Something went wrong. Try again."),
        )
        return _error_response(
            request, error.status_code, code, message, None, exception=error
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(
        request: Request, error: Exception
    ) -> JSONResponse:
        return _error_response(
            request,
            500,
            "INTERNAL_SERVER_ERROR",
            "Something went wrong. Try again.",
            None,
            exception=error,
        )
