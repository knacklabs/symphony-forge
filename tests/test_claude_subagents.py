"""Claude workers receive helper budgets through the Agent SDK.

Test-audit answers:
1. Protects Claude's observable SDK helper definitions, initialized helper defaults, unchanged
   Codex settings, and the absence of process-wide Claude settings.
2. A Claude turn can omit its helper agents, use the wrong model or effort, change its helper
   budget after a failure, leak a setting into the repo or home, or accept half of a config pair.
3. Existing worker tests cover the SDK turn and Codex settings separately, but none checks Claude
   helper definitions at the SDK request boundary or their init/adoption rules.
4. The tests call Forge commands and inspect the SDK stub's external request; they add no
   production seam.
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from conftest import _install_claude_sdk
from test_effort_ladder import _round_client
from test_setup import _fresh_client
from test_task import story
from test_worker import calls, install_claude
from test_codex_worker import sdk_data  # noqa: F401

pytestmark = pytest.mark.platform

HELPER_ROLES = {
    "worker", "fixer", "coder", "frontend", "tester", "refactorer", "explorer",
    "planner", "architect", "debugger", "security", "performance", "reader",
    "general-purpose",
}


def _new_claude_task(repo, gh, tmp_path, monkeypatch, sdk_data, task="PAGE"):
    """An initialized client whose worker uses the init-written model defaults."""
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.path = client
    repo.write("forge.local.toml", 'tools = "claude"\nworkers = "claude"\n')
    _install_claude_sdk(repo.bin, sdk_data)
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    monkeypatch.setenv("PYTHONPATH", str(repo.bin) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    log = install_claude(repo)
    story(repo)
    started = repo.forge("task", "start", f"BOARD/{task}")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    return client, folder, log


def _expected_agents(model: str, effort: str) -> dict[str, dict[str, str]]:
    return {name: {"model": model, "effort": effort} for name in HELPER_ROLES}


def _agent_budgets(agents: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    return {name: {key: definition[key] for key in ("model", "effort")}
            for name, definition in agents.items()}


@pytest.mark.parametrize("case", ["new-init-design", "new-configured-retry", "adopted-configured-retry"])
def test_6_claude_builder_gets_haiku_helpers(repo, gh, tmp_path, monkeypatch, sdk_data, case):
    if case == "new-init-design":
        client, folder, log = _new_claude_task(repo, gh, tmp_path, monkeypatch, sdk_data)
        built = repo.forge("work", "BOARD/PAGE")
        assert built.returncode == 0, built.stdout + built.stderr
        [sent] = calls(log)
        assert _agent_budgets(sent["options"]["agents"]) == _expected_agents(
            "claude-haiku-5-5", "high")

        initialized_models = tomllib.loads((client / "forge.toml").read_text("utf-8"))["models"]
        for kind in ("build", "fix", "lite"):
            assert initialized_models[kind]["claude"]["subagents"] == "claude-haiku-5-5"
            assert initialized_models[kind]["claude"]["subagent_effort"] == "high"
        return

    # Explicit helper pairs stay the same on new and earlier-adopted clients, including retries.
    history = "adopted" if case.startswith("adopted") else "new"
    env, folder, log = _round_client(repo, gh, tmp_path, monkeypatch, "claude", history=history,
                                     sdk_data=sdk_data)
    config = folder / "forge.toml"
    text = config.read_text("utf-8")
    text = text.replace(
        'models.build = { model = "claude-sonnet-5-5", effort = "low" }',
        'models.build = { model = "claude-sonnet-5-5", effort = "low", '
        'subagents = "custom-haiku", subagent_effort = "medium" }')
    assert 'subagents = "custom-haiku", subagent_effort = "medium"' in text
    config.write_text(text, encoding="utf-8")
    repo.git("add", "forge.toml", cwd=folder)
    repo.git("commit", "-q", "-m", "Keep the Claude helper budget", cwd=folder)
    configured = config.read_bytes()
    (folder / "web/help.py").parent.mkdir(parents=True, exist_ok=True)
    (folder / "web/help.py").write_text("HELP = 'round one'\n", encoding="utf-8")
    (folder / "fail_test.py").write_text(
        "print('intentional failed close test')\nraise SystemExit(1)\n", encoding="utf-8")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "1")
    first = repo.forge("work", "BOARD/HELP")
    assert first.returncode == 0, first.stdout + first.stderr
    failed = env.close("BOARD/HELP")
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "intentional failed close test" in failed.stdout
    monkeypatch.delenv("STUB_CLAUDE_COMMIT_FROM", raising=False)
    retry = repo.forge("work", "BOARD/HELP")
    assert retry.returncode == 0, retry.stdout + retry.stderr
    [initial, retried] = calls(log)
    assert _agent_budgets(initial["options"]["agents"]) == _expected_agents("custom-haiku", "medium")
    assert retried["options"]["agents"] == initial["options"]["agents"]
    assert config.read_bytes() == configured


def test_6_codex_request_names_the_subagents(repo, gh, tmp_path, monkeypatch, sdk_data, claude_session):
    _, _, log = _round_client(repo, gh, tmp_path, monkeypatch, "codex", sdk_data=sdk_data)
    worked = repo.forge("work", "BOARD/HELP")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    from test_codex_worker import _sent

    [started] = _sent(log, "thread/start")
    assert started["config"]["agents.default_subagent_model"] == "gpt-6-luna"
    assert started["config"]["agents.default_subagent_reasoning_effort"] == "max"
    assert not (repo.bin / "claude-sdk-calls.jsonl").exists()


def test_6_no_process_wide_setting(repo, gh, tmp_path, monkeypatch, sdk_data):
    home = tmp_path / "home"
    claude_config = tmp_path / "claude-config"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_config))
    monkeypatch.delenv("CLAUDE_CODE_SUBAGENT_MODEL", raising=False)
    _, folder, log = _round_client(repo, gh, tmp_path, monkeypatch, "claude", history="adopted",
                                   sdk_data=sdk_data)
    # A different kind's pair must not replace the default for this build kind.
    config = folder / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'models.lite = { model = "claude-sonnet-5-5", effort = "low" }',
        'models.lite = { model = "claude-sonnet-5-5", effort = "low", '
        'subagents = "custom-haiku", subagent_effort = "medium" }'), encoding="utf-8")
    repo.git("add", "forge.toml", cwd=folder)
    repo.git("commit", "-q", "-m", "Keep a separate lite helper budget", cwd=folder)
    settings = [folder / ".claude/settings.json", home / ".claude/settings.json",
                claude_config / "settings.json"]
    before = {path: path.read_bytes() if path.exists() else None for path in settings}
    worked = repo.forge("work", "BOARD/HELP")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    [sent] = calls(log)
    assert _agent_budgets(sent["options"]["agents"]) == _expected_agents("claude-haiku-5-5", "high")
    assert {path: path.read_bytes() if path.exists() else None for path in settings} == before
    assert "CLAUDE_CODE_SUBAGENT_MODEL" not in sent["options"].get("env", {})
    assert sent["process_env"]["CLAUDE_CODE_SUBAGENT_MODEL"] is None


def test_6_one_key_is_refused_as_today(repo, gh, tmp_path, monkeypatch, sdk_data):
    _, folder, _ = _round_client(repo, gh, tmp_path, monkeypatch, "claude", history="adopted",
                                 sdk_data=sdk_data)
    config = folder / "forge.toml"
    text = config.read_text("utf-8")
    text = text.replace(
        'models.build = { model = "claude-sonnet-5-5", effort = "low" }',
        'models.build = { model = "claude-sonnet-5-5", effort = "low", '
        'subagents = "claude-haiku-5-5" }')
    assert 'subagents = "claude-haiku-5-5" }' in text
    config.write_text(text, encoding="utf-8")

    refused = repo.forge("work", "BOARD/HELP")

    assert refused.returncode == 1
    assert "models.build sets only one of subagents and subagent_effort" in refused.stderr
