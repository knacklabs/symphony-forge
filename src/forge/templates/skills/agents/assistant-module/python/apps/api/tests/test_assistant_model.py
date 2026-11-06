"""The optional assistant uses its settings, monthly usage and plain-text guard."""

import asyncio
import json
import re
import subprocess
import textwrap
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker
from test_api import sign_up

from app.assistant import assistant_lifespan
from app.assistant.guard import contains_secret
from app.assistant.model import create_model, load_settings
from app.assistant.prompt import PROMPT_VERSION, SYSTEM_PROMPT

API = Path(__file__).resolve().parents[1]
ASSISTANT = API / "app" / "assistant"
SETTINGS = {
    "ASSISTANT_AI_KEY": "test-model-key",
    "ASSISTANT_MODEL": "test-model",
    "ASSISTANT_SPEND_CAP_USD": "10",
    "ASSISTANT_PRICE_INPUT_USD_PER_MTOK": "0.15",
    "ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK": "0.60",
}
KEY_SHAPE = re.compile(r"(?<![A-Za-z0-9])sk-(?:proj-)?[A-Za-z0-9_-]{20,}")


def test_only_the_model_settings_read_the_assistant_key() -> None:
    readers = [
        path.relative_to(API).as_posix()
        for path in sorted((API / "app").rglob("*.py"))
        if "ASSISTANT_AI_KEY" in path.read_text(encoding="utf-8")
    ]
    assert readers == ["app/assistant/model.py"]


def test_the_assistant_module_contains_no_provider_key() -> None:
    for path in sorted(ASSISTANT.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".md"}:
            assert not KEY_SHAPE.search(path.read_text(encoding="utf-8")), path


def test_missing_model_settings_stop_assistant_startup_with_plain_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def start() -> None:
        factory: sessionmaker[Session] = sessionmaker()
        async with assistant_lifespan(factory, "postgresql://unused", "test"):
            pass

    expected = {
        "ASSISTANT_AI_KEY": "ASSISTANT_AI_KEY must be set.",
        "ASSISTANT_MODEL": "ASSISTANT_MODEL must be set.",
        "ASSISTANT_SPEND_CAP_USD": "ASSISTANT_SPEND_CAP_USD must be set.",
        "ASSISTANT_PRICE_INPUT_USD_PER_MTOK": "ASSISTANT_PRICE_INPUT_USD_PER_MTOK must be set.",
        "ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK": "ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK must be set.",
    }
    invalid = {
        "-1": "ASSISTANT_SPEND_CAP_USD must be a finite non-negative number.",
        "NaN": "ASSISTANT_SPEND_CAP_USD must be a finite non-negative number.",
        "Infinity": "ASSISTANT_SPEND_CAP_USD must be a finite non-negative number.",
        "oops": "ASSISTANT_SPEND_CAP_USD must be a finite non-negative number.",
        "0.0000001": "ASSISTANT_SPEND_CAP_USD must use at most six decimal places.",
    }
    for missing, message in expected.items():
        with monkeypatch.context() as patch:
            for name, value in SETTINGS.items():
                patch.setenv(name, value)
            patch.delenv(missing, raising=False)
            with pytest.raises(RuntimeError) as error:
                asyncio.run(start())
            assert str(error.value) == message
    for cap, message in invalid.items():
        with monkeypatch.context() as patch:
            for name, value in SETTINGS.items():
                patch.setenv(name, value)
            patch.setenv("ASSISTANT_SPEND_CAP_USD", cap)
            with pytest.raises(RuntimeError) as error:
                asyncio.run(start())
            assert str(error.value) == message
    with monkeypatch.context() as patch:
        for name, value in SETTINGS.items():
            patch.setenv(name, value)
        patch.setenv("ASSISTANT_AI_URL", "https://user:password@example.test/v1")
        with pytest.raises(RuntimeError) as error:
            asyncio.run(start())
        assert str(error.value) == (
            "ASSISTANT_AI_URL must be an HTTP or HTTPS URL without credentials."
        )


def test_the_model_uses_its_configured_key_model_and_prices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in SETTINGS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("ASSISTANT_AI_URL", "https://models.example.test/v1")
    settings = load_settings()
    model = create_model(settings)

    assert settings.key.get_secret_value() == SETTINGS["ASSISTANT_AI_KEY"]
    assert settings.model == SETTINGS["ASSISTANT_MODEL"]
    assert settings.cap_micros == 10_000_000
    assert settings.input_usd_per_mtok == Decimal("0.15")
    assert settings.output_usd_per_mtok == Decimal("0.60")
    assert settings.cost_micros(1, 1) == 1
    assert settings.cost_micros(1_000_000, 1_000_000) == 750_000
    assert model.model_name == settings.model
    assert model.openai_api_key == settings.key
    assert model.openai_api_base == "https://models.example.test/v1"


def test_the_monthly_cap_counts_current_usage_across_accounts_only(
    client: httpx.Client,
) -> None:
    first, _ = sign_up(client)
    second, _ = sign_up(client)
    source = f"""
import json
from datetime import UTC, datetime, timedelta
from sqlalchemy import delete, select

import app.auth  # noqa: F401
from app.assistant import Usage, UsageService
from app.assistant.model import load_settings as load_model_settings
from app.core import (
    AccountPrincipal,
    create_database,
    load_settings as load_app_settings,
)
from app.organisations.models import Membership

settings = load_model_settings()
app_settings = load_app_settings()
engine, session_factory = create_database(app_settings.database_url)
now = datetime(2001, 1, 1, tzinfo=UTC)
ids = []
try:
    with session_factory() as db:
        principals = []
        for email in ({json.dumps(first["email"])}, {json.dumps(second["email"])}):
            member = db.scalar(select(Membership).where(Membership.email == email))
            assert member is not None
            principals.append(AccountPrincipal(
                member.account_id, member.email, member.organisation_id, member.role
            ))
        usage = UsageService(db)
        ids.append(usage.record(principals[0], settings.cap_micros // 2, now).id)
        before_cap = usage.month_cost_micros(now)
        can_start_before_cap = usage.can_start(settings, now)
        ids.append(usage.record(principals[1], settings.cap_micros - settings.cap_micros // 2, now).id)
        ids.append(usage.record(principals[0], settings.cap_micros, now - timedelta(seconds=1)).id)
        current = usage.month_cost_micros(now)
        can_start = usage.can_start(settings, now)
    print(json.dumps({{
        "before_cap": before_cap,
        "can_start_before_cap": can_start_before_cap,
        "current": current,
        "can_start": can_start,
    }}))
finally:
    if ids:
        with session_factory.begin() as db:
            db.execute(delete(Usage).where(Usage.id.in_(ids)))
    engine.dispose()
"""
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose.test.yml",
            "exec",
            "-T",
            "api",
            "uv",
            "run",
            "--no-sync",
            "python",
            "-",
        ],
        cwd="../..",
        input=textwrap.dedent(source),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=30,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, f"The assistant usage call failed: {output}"
    assert json.loads(result.stdout) == {
        "before_cap": 5_000_000,
        "can_start_before_cap": True,
        "current": 10_000_000,
        "can_start": False,
    }


def test_the_prompt_is_bounded_and_secrets_are_refused() -> None:
    assert PROMPT_VERSION
    assert len(SYSTEM_PROMPT.encode("utf-8")) < 12 * 1024
    assert contains_secret("My password is hunter2")
    assert contains_secret("My card number is 4111 1111 1111 1111")
    assert not contains_secret("How many active projects do we have?")
