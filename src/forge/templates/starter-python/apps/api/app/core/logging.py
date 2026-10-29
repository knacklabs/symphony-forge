import json
import sys
from datetime import UTC, datetime
from typing import Literal

from fastapi import Request

from app.core.config import Settings

LogLevel = Literal["debug", "info", "warn", "error", "fatal"]
_LEVELS = {"debug": 0, "info": 1, "warn": 2, "error": 3, "fatal": 4}
_log_level = "info"


def set_log_level(level: str) -> None:
    global _log_level
    _log_level = level


def _remove_secrets(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: "[removed]"
            if any(
                word in key.lower().replace("_", "").replace("-", "")
                for word in ("password", "token", "secret", "key", "authorization")
            )
            else _remove_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_remove_secrets(item) for item in value]
    return value


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
    if _LEVELS[level] < _LEVELS[_log_level]:
        return
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
        "context": _remove_secrets(context),
        "environment": environment
        or (settings.app_env if settings is not None else "unknown"),
        "serviceName": "api",
        "module": module,
        "correlationId": correlation_id,
    }
    sys.stdout.write(json.dumps(record, separators=(",", ":")) + "\n")
    sys.stdout.flush()
