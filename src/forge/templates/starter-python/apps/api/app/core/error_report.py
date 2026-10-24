from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.core.envelope import ErrorEnvelope, SuccessEnvelope
from app.core.logging import log_event


class ErrorReportInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(
        max_length=200,
        description="The class name of the error.",
        examples=["TypeError"],
    )
    path: str = Field(
        max_length=2000,
        description="The page path where it happened.",
        examples=["/projects"],
    )


class ErrorReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    error_id: UUID = Field(
        alias="errorId",
        description="The reference for this error report.",
        examples=["d49fe9c4-a93b-4e3d-a20a-1afc37f4d1c0"],
    )


def report_error(
    request: Request,
    *,
    source: Literal["api", "web"],
    name: str,
    path: str,
    error_id: UUID,
    method: str | None = None,
    status: int | None = None,
) -> None:
    context: dict[str, object] = {
        "errorId": str(error_id),
        "source": source,
        "name": name,
        "path": path.split("?", 1)[0].split("#", 1)[0],
    }
    if method is not None:
        context["method"] = method
    if status is not None:
        context["status"] = status
    log_event(request, "error", "Error report", "app.core.error_report", context)


router = APIRouter(prefix="/api/v1/error-reports", tags=["Error reports"])


@router.post(
    "",
    status_code=201,
    response_model=SuccessEnvelope[ErrorReportResponse],
    responses={
        400: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        429: {"model": ErrorEnvelope},
    },
    summary="Record a web error report.",
    description="Logs the error kind and page path without error text or a query string.",
)
def create_error_report(
    report: ErrorReportInput, request: Request
) -> SuccessEnvelope[ErrorReportResponse]:
    error_id = uuid4()
    report_error(
        request,
        source="web",
        name=report.name,
        path=report.path,
        error_id=error_id,
    )
    return SuccessEnvelope(data=ErrorReportResponse(error_id=error_id))
