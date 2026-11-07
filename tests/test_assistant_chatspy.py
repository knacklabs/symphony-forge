"""The copied Python assistant keeps chats private and runs in a new app."""

import shutil
from pathlib import Path

import pytest

from assistant_copy_python import copy_assistant_python, prepare_assistant_python_run
from test_agent_ready import _new_client
from test_starter_tree import LIVE, _require_cases, _run_live_starter

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "src/forge/templates/skills/agents/assistant-module/python"
STORY = "FORGE-ASSIST-1-PYCHAT"
ASSISTANT_SETTINGS = {
    "ASSISTANT_AI_KEY": "test-key",
    "ASSISTANT_MODEL": "test-model",
    "ASSISTANT_SPEND_CAP_USD": "10",
    "ASSISTANT_PRICE_INPUT_USD_PER_MTOK": "0.15",
    "ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK": "0.60",
}


def _assistant_client(repo, gh, tmp_path: Path) -> Path:
    client = _new_client(repo, gh, tmp_path, "python")
    assert not (client / "apps/api/app/assistant").exists()
    assert not (client / "libs/assistant").exists()
    shutil.copytree(
        TEMPLATE,
        client / ".codex/skills/agents/assistant-module/python",
        dirs_exist_ok=True,
    )
    copy_assistant_python(client)
    return client


def _prepare_assistant_app(client: Path, monkeypatch) -> None:
    prepare_assistant_python_run(client)
    for name, value in ASSISTANT_SETTINGS.items():
        monkeypatch.setenv(name, value)
    compose = client / "compose.test.yml"
    compose_text = compose.read_text(encoding="utf-8")
    settings = "".join(f"      {name}: ${{{name}}}\n" for name in ASSISTANT_SETTINGS)
    marker = '      PORT: "3000"\n'
    if compose_text.count(marker) != 3:
        raise AssertionError(f"copy step did not match all API services in {compose}")
    compose.write_text(
        compose_text.replace(marker, marker + settings), encoding="utf-8"
    )
    monkeypatch.setenv("CI", "true")


def _run_assistant_app(client: Path, tmp_path_factory, monkeypatch):
    _prepare_assistant_app(client, monkeypatch)
    return _run_live_starter(tmp_path_factory, [(client, Path("."))])


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_4_python_chats_are_private(repo, gh, tmp_path, tmp_path_factory, monkeypatch):
    # Audit: the copied Python API must list only the caller's chats and hide a chat from a
    # same-organisation member and an admin. Starter and retention cases do not own that rule.
    # This uses the real HTTP tests after applying the README steps, with no test seam.
    client = _assistant_client(repo, gh, tmp_path)
    assert (client / "apps/api/tests/test_assistant_api.py").is_file()
    if not LIVE:
        return

    cases = _run_assistant_app(client, tmp_path_factory, monkeypatch)["api"]
    _require_cases(
        cases,
        (
            "test_a_person_lists_only_their_own_chats",
            "test_a_person_reads_messages_and_a_pending_confirmation",
            "test_another_person_and_an_admin_get_404_for_a_chat",
        ),
    )


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_6_python_the_template_copies_in_and_runs(
    repo, gh, tmp_path, tmp_path_factory, monkeypatch
):
    # Audit: a fresh Python app must have no assistant before copying, then the copied module
    # must compile, start with Postgres and pass its HTTP and retention cases. Existing Python
    # starter smoke tests do not include this optional module. No test-only production seam is used.
    client = _assistant_client(repo, gh, tmp_path)
    assert (client / "apps/api/app/assistant/schema.py").is_file()
    assert (client / "apps/api/app/assistant/routes.py").is_file()
    assert (client / "libs/assistant/contracts/src/index.ts").is_file()
    assert (client / "apps/api/tests/test_assistant_api.py").is_file()
    if not LIVE:
        return

    enabled = _run_assistant_app(client, tmp_path_factory, monkeypatch)
    _require_cases(
        enabled["api"],
        (
            "test_creates_lists_reads_updates_and_deletes_a_project",
            "test_a_person_lists_only_their_own_chats",
            "test_a_person_reads_messages_and_a_pending_confirmation",
            "test_another_person_and_an_admin_get_404_for_a_chat",
            "test_a_chat_31_days_after_its_last_message_is_deleted_with_its_checkpoints",
            "test_a_chat_29_days_after_its_last_message_stays",
            "test_a_new_message_moves_the_30_days",
            "test_python_stream_events_match_the_typescript_contracts",
        ),
    )

    disabled = tmp_path / "assistant-disabled"
    disabled.mkdir()
    for name in (*ASSISTANT_SETTINGS, "ASSISTANT_AI_URL"):
        monkeypatch.delenv(name, raising=False)
    disabled_client = _new_client(repo, gh, disabled, "python")
    disabled_result = _run_live_starter(
        tmp_path_factory, [(disabled_client, Path("."))]
    )
    _require_cases(
        disabled_result["api"],
        ("test_creates_lists_reads_updates_and_deletes_a_project",),
    )
