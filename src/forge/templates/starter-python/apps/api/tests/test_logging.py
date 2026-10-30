import json

import pytest

from app.core.logging import LogLevel, log_event, set_log_level


# Audit: stdout filtering owns all level outputs. Wrong comparisons or suppressed
# fatal regress this; config/HTTP tests do not cover these outputs. No test seam.
def test_the_logger_writes_nothing_below_the_log_level(
    capsys: pytest.CaptureFixture[str],
) -> None:
    levels: tuple[LogLevel, ...] = ("debug", "info", "warn", "error", "fatal")
    try:
        set_log_level("warn")
        for level in levels[:2]:
            log_event(None, level, "Below threshold", "test", {})
        assert capsys.readouterr().out == ""
        for level in levels[2:]:
            log_event(None, level, "At threshold or above", "test", {})
        assert [
            json.loads(line)["level"] for line in capsys.readouterr().out.splitlines()
        ] == ["warn", "error", "fatal"]
    finally:
        set_log_level("info")


# Audit: public log output owns recursive redaction. A nested/normalized key can
# bypass removal; HTTP cases supply no arbitrary details. No production seam.
def test_the_logger_removes_password_token_secret_key_and_authorization_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    context: dict[str, object] = {
        "password": "p",
        "resetToken": "t",
        "client_secret": "s",
        "apiKey": "k",
        "Authorization": "a",
        "nested": [{"newPassword": "n"}],
        "projectId": "x",
        "to-ken": "hyphen-secret",
    }
    log_event(None, "info", "Project details", "test", context)
    output = capsys.readouterr().out
    assert json.loads(output)["context"] == {
        "password": "[removed]",
        "resetToken": "[removed]",
        "client_secret": "[removed]",
        "apiKey": "[removed]",
        "Authorization": "[removed]",
        "nested": [{"newPassword": "[removed]"}],
        "projectId": "x",
        "to-ken": "[removed]",
    }
    for value in ("p", "t", "s", "k", "a", "n", "hyphen-secret"):
        assert json.dumps(value) not in output
