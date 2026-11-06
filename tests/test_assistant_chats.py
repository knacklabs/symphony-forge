"""The copied TypeScript assistant keeps chats private and runs in a new app."""
import shutil
from pathlib import Path

import pytest

from assistant_copy import copy_assistant
from test_agent_ready import _new_client
from test_starter_tree import LIVE, _require_cases, _run_live_starter

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "src/forge/templates/skills/agents/assistant-module/typescript"
STORY = "FORGE-ASSIST-1-TSCHAT"


def _assistant_client(repo, gh, tmp_path):
    client = _new_client(repo, gh, tmp_path)
    assert not (client / "libs/assistant").exists()
    shutil.copytree(
        TEMPLATE,
        client / ".codex/skills/agents/assistant-module/typescript",
        dirs_exist_ok=True,
    )
    copy_assistant(client)
    return client


ASSISTANT_SETTINGS = {
    "ASSISTANT_AI_KEY": "test-key",
    "ASSISTANT_MODEL": "test-model",
    "ASSISTANT_SPEND_CAP_USD": "10",
    "ASSISTANT_PRICE_INPUT_USD_PER_MTOK": "0.15",
    "ASSISTANT_PRICE_OUTPUT_USD_PER_MTOK": "0.60",
}


def _run_assistant_app(client, tmp_path_factory, monkeypatch, *, settings=None):
    script = client / "scripts/test.mjs"
    script.write_text(
        script.read_text(encoding="utf-8").replace(
            "['pnpm', 'install', '--frozen-lockfile']",
            "['pnpm', 'install', '--no-frozen-lockfile']",
        ),
        encoding="utf-8",
    )
    assistant_settings = ASSISTANT_SETTINGS | (settings or {})
    for name, value in assistant_settings.items():
        monkeypatch.setenv(name, value)
    compose = client / "compose.test.yml"
    compose_text = compose.read_text(encoding="utf-8")
    setting_lines = "".join(f"      {name}: ${{{name}}}\n" for name in assistant_settings)
    marker = '      PORT: "3000"\n'
    if compose_text.count(marker) != 3:
        raise AssertionError(f"copy step did not match all API services in {compose}")
    compose.write_text(compose_text.replace(marker, marker + setting_lines), encoding="utf-8")
    monkeypatch.setenv("CI", "true")
    return _run_live_starter(tmp_path_factory, [(client, Path("."))])


def _disable_assistant(client: Path) -> None:
    app_module = client / "apps/api/src/app.module.ts"
    source = app_module.read_text(encoding="utf-8")
    for line in (
        "import { AssistantModule } from '@app/assistant-server';\n",
        "    AssistantModule,\n",
    ):
        if source.count(line) != 1:
            raise AssertionError(f"copy step did not match one location in {app_module}")
        source = source.replace(line, "")
    app_module.write_text(source, encoding="utf-8")
    compose = client / "compose.test.yml"
    compose_text = compose.read_text(encoding="utf-8")
    for name in ASSISTANT_SETTINGS:
        line = f"      {name}: ${{{name}}}\n"
        if compose_text.count(line) != 3:
            raise AssertionError(f"copy step did not match all API services in {compose}")
        compose_text = compose_text.replace(line, "")
    compose.write_text(compose_text, encoding="utf-8")
    for name in ("assistant-api.e2e-spec.ts", "assistant-chats.e2e-spec.ts"):
        (client / "apps/api/test" / name).unlink()


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_4_chats_are_private(repo, gh, tmp_path, tmp_path_factory, monkeypatch):
    # Audit: the running API and Postgres own chat privacy. Existing retention and
    # agent-ready tests do not cover listing or reading a chat as another account.
    # No test-only production seam is needed.
    client = _assistant_client(repo, gh, tmp_path)
    assert (client / "apps/api/test/assistant-api.e2e-spec.ts").is_file()
    if not LIVE:
        return

    cases = _run_assistant_app(client, tmp_path_factory, monkeypatch)["api"]
    _require_cases(cases, (
        "a person lists only their own chats",
        "a person reads messages and a pending confirmation",
        "another person and an admin get 404 for a chat",
    ))


@pytest.mark.platform
@pytest.mark.timeout(1800)
def test_6_the_template_copies_in_and_runs(repo, gh, tmp_path, tmp_path_factory, monkeypatch):
    # Audit: a copied module must compile and pass its real API cases. A fresh
    # starter run separately proves the optional module needs no settings when off.
    # No source-content assertion or test-only production seam is used.
    client = _assistant_client(repo, gh, tmp_path)
    assert (client / "libs/assistant/contracts").is_dir()
    assert (client / "libs/assistant/server/src/assistant.module.ts").is_file()
    assert (client / "libs/assistant/server/src/assistant.chats.controller.ts").is_file()
    if not LIVE:
        return

    enabled = _run_assistant_app(client, tmp_path_factory, monkeypatch)
    _require_cases(enabled["api"], (
        "a person lists only their own chats",
        "a person reads messages and a pending confirmation",
        "another person and an admin get 404 for a chat",
        "a chat 31 days after its last message is deleted with its checkpoints",
        "a chat 29 days after its last message stays",
        "a new message moves the 30 days",
    ))
    disabled = tmp_path / "assistant-disabled"
    shutil.copytree(client, disabled)
    _disable_assistant(disabled)
    for name in (*ASSISTANT_SETTINGS, "ASSISTANT_AI_URL"):
        monkeypatch.delenv(name, raising=False)
    disabled_result = _run_live_starter(tmp_path_factory, [(disabled, Path("."))])
    _require_cases(disabled_result["api"], (
        "creates, lists, reads, updates, and deletes a project through the API",
    ))
