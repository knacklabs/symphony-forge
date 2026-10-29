"""The starters log API requests safely, and sync leaves old apps alone."""

from pathlib import Path

import pytest

from test_mcp import _adopted_files_after_sync
from test_setup import _fresh_client
from test_starter_tree import LIVE, _junit_cases, _require_cases, live_python_run, live_run


REQUEST_CASE = "each API request writes one log line without its query string"
LEVEL_CASES = (
    "LOG_LEVEL defaults to info and accepts debug, info, warn or error",
    "LOG_LEVEL refuses an unsupported value",
)
LEVEL_UNIT_CASE = "the logger writes nothing below LOG_LEVEL"
REMOVAL_UNIT_CASE = "the logger removes password, token, secret, key and authorization values"
LOGGER = Path("libs/core/server/src/common/json-logger.ts")
REQUEST_MIDDLEWARE = Path("libs/core/server/src/common/request-log.middleware.ts")


def _adopted_after_sync(repo):
    """Put app-owned settings and logger code beside the earlier-adopted fixture before sync."""
    env_example = repo.write(".env.example", "APP_ORIGIN=http://old-client.test\nLOG_LEVEL=warn\n")
    logger = repo.write(LOGGER.as_posix(), "export const adoptedLogger = 'unchanged';\n")
    repo.write("apps/api/src/main.ts", "export const adoptedMain = 'unchanged';\n")
    env_before = env_example.read_bytes()
    logger_before = logger.read_bytes()
    before, after, _, _, _ = _adopted_files_after_sync(repo, include_sync_status=True)
    assert after == before
    assert env_example.read_bytes() == env_before
    assert logger.read_bytes() == logger_before
    assert not (repo.path / REQUEST_MIDDLEWARE).exists()
    return before, after


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python", "earlier adopted"])
def test_1_each_api_request_writes_one_log_line(repo, gh, tmp_path, tmp_path_factory, starter):
    # Audit: protects the shipped-app request log contract and adopted-app preservation. A
    # missing middleware or a sync that edits app code can regress this; existing starter tests
    # do not assert request log output. The live API report owns the HTTP behavior. No production
    # seam is needed.
    if starter == "earlier adopted":
        _adopted_after_sync(repo)
        return

    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "python" if starter == "python" else "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    if starter == "python":
        assert '"API request"' in (client / "apps/api/app/core/security.py").read_text(encoding="utf-8")
    else:
        assert (client / REQUEST_MIDDLEWARE).is_file()
    if LIVE:
        live = (live_python_run if starter == "python" else live_run)(tmp_path_factory)
        _require_cases(live["api"], ("test_each_api_request_writes_one_log_line_without_its_query_string" if starter == "python" else REQUEST_CASE,))


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python", "earlier adopted"])
def test_2_the_log_level_picks_the_lowest_level_written(
    repo, gh, tmp_path, tmp_path_factory, starter
):
    # Audit: protects the generated default and the API's accepted/refused startup settings. A
    # missing default or unsupported value accepted at startup can regress it; no existing case
    # owns LOG_LEVEL. The live API and format reports prove the config and write boundary. No
    # production seam is needed.
    if starter == "earlier adopted":
        _adopted_after_sync(repo)
        return

    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "python" if starter == "python" else "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert "LOG_LEVEL=info" in (client / ".env.example").read_text(encoding="utf-8").splitlines()
    if LIVE:
        live = (live_python_run if starter == "python" else live_run)(tmp_path_factory)
        if starter == "python":
            _require_cases(live["api"], (
                "test_log_level_defaults_to_info_and_accepts_debug_info_warn_or_error",
                "test_log_level_refuses_an_unsupported_value",
                "test_the_logger_writes_nothing_below_the_log_level",
            ))
        else:
            _require_cases(live["api"], LEVEL_CASES)
            _require_cases(_junit_cases(live["folder"] / "test-results/formats.xml"), (LEVEL_UNIT_CASE,))


@pytest.mark.platform
@pytest.mark.timeout(1800)
@pytest.mark.parametrize("starter", ["typescript", "python", "earlier adopted"])
def test_3_secret_values_never_reach_the_logs(
    repo, gh, tmp_path, tmp_path_factory, starter
):
    # Audit: protects redaction at the logger boundary and preserves a logger in an adopted app.
    # A later log call could leak a protected field, while sync could overwrite an app logger;
    # no existing case owns either contract. The format report owns the live redaction case. No
    # production seam is needed.
    if starter == "earlier adopted":
        before, after = _adopted_after_sync(repo)
        assert before[LOGGER] == after[LOGGER]
        return

    client, initialized = _fresh_client(repo, gh, tmp_path, "--starter", "python" if starter == "python" else "react")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    if LIVE:
        live = (live_python_run if starter == "python" else live_run)(tmp_path_factory)
        if starter == "python":
            _require_cases(live["api"], ("test_the_logger_removes_password_token_secret_key_and_authorization_values",))
        else:
            _require_cases(_junit_cases(live["folder"] / "test-results/formats.xml"), (REMOVAL_UNIT_CASE,))
