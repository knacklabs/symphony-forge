"""Application settings validation at the API start boundary."""

import pytest

from app.core.config import load_settings


def valid_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:password@localhost/test")
    monkeypatch.setenv("APP_ORIGIN", "http://127.0.0.1:3000")
    monkeypatch.setenv("PORT", "3000")


def test_defaults_to_many_and_accepts_one_or_many(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_environment(monkeypatch)
    monkeypatch.delenv("APP_COMPANIES", raising=False)
    assert load_settings().app_companies == "many"

    for companies in ("one", "many"):
        monkeypatch.setenv("APP_COMPANIES", companies)
        assert load_settings().app_companies == companies


def test_rejects_an_unsupported_companies_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_environment(monkeypatch)
    monkeypatch.setenv("APP_COMPANIES", "some")

    with pytest.raises(RuntimeError, match="APP_COMPANIES must be one or many\\."):
        load_settings()


# Audit: startup config owns defaults and rejected levels. Missing validation
# regresses this; existing company cases cannot detect it. No production seam.
def test_log_level_defaults_to_info_and_accepts_debug_info_warn_or_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_environment(monkeypatch)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert load_settings().log_level == "info"
    for level in ("debug", "info", "warn", "error"):
        monkeypatch.setenv("LOG_LEVEL", level)
        assert load_settings().log_level == level


def test_log_level_refuses_an_unsupported_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid_environment(monkeypatch)
    monkeypatch.setenv("LOG_LEVEL", "verbose")
    with pytest.raises(
        RuntimeError, match="LOG_LEVEL must be debug, info, warn or error\\."
    ):
        load_settings()
