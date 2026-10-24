import json
import sys
from datetime import UTC, datetime
from typing import Literal

from fastapi import Request

from app.core.config import Settings

LogLevel = Literal["debug", "info", "warn", "error", "fatal"]


def log_event(
    request: Request | None,
    level: LogLevel,
    message: str,
    module: str,
    context: dict[str, object],
    *,
    environment: str | None = None,
    correlation_id: str | None = None,
) -> None:
    settings: Settings | None = None
    if request is not None:
        settings = getattr(request.app.state, "settings", None)
        correlation_id = correlation_id or getattr(
            request.state, "correlation_id", None
        )
    record = {
        "timestampUtc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "level": level,
        "message": message,
        "context": context,
        "environment": environment
        or (settings.app_env if settings is not None else "unknown"),
        "serviceName": "api",
        "module": module,
        "correlationId": correlation_id,
    }
    sys.stdout.write(json.dumps(record, separators=(",", ":")) + "\n")
    sys.stdout.flush()
