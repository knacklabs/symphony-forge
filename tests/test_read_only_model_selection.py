"""Read-only work has its own models while a fix's first build keeps lite."""
from __future__ import annotations

import json
import os
import tomllib

import pytest

from conftest import ROOT, _install
from test_close import env  # noqa: F401
from test_codex_worker import QUIET, _codex_repo, _sent, sdk_data  # noqa: F401
from test_setup import _fresh_client
from test_subagent_roles import _settings, _synced
from test_upgrade_command import (  # noqa: F401
    _repo_adopted_on_the_previous_release, unsynced_up, up,
)
from test_worker import calls, install_claude

STORY = "explore-kind"
MODELS = """
[models.lite.codex]
model = "gpt-6-sol"
effort = "low"

[models.lite.claude]
model = "sonnet"
effort = "medium"

[models.explore.codex]
model = "gpt-6-luna"
effort = "high"

[models.explore.claude]
model = "claude-haiku-5-5"
effort = "high"
"""


def _sdk(repo, monkeypatch, sdk_data, checkout):
    _install(repo.bin, "codex-app-server",
             (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    home = repo.path.parent / "explore-codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(checkout))}]\ntrust_level = "trusted"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))
    return repo.bin / "codex-app-server.jsonl"


def test_1_init_gives_read_only_work_explore_defaults(repo, gh, tmp_path):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    models = tomllib.loads((client / "forge.toml").read_text("utf-8"))["models"]
    assert models["explore"]["claude"] == {"model": "claude-haiku-5-5", "effort": "high"}
    assert models["explore"]["codex"] == models["lite"]["codex"]
    assert _settings(client, "explorer") == (
        ("gpt-6.1-sol", "medium"), ("claude-haiku-5-5", "high"))


def test_2_sync_writes_explorer_from_explore_for_both_hosts(repo):
    synced = _synced(repo, MODELS)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert _settings(repo.path, "explorer") == (
        ("gpt-6-luna", "high"), ("claude-haiku-5-5", "high"))
    # Changing only read-only settings reaches both roles on the next sync.
    toml = repo.path / "forge.toml"
    repo.write("forge.toml", toml.read_text("utf-8").replace(
        '"gpt-6-luna"', '"gpt-6.1-sol"').replace('"claude-haiku-5-5"', '"haiku"'))
    again = repo.forge("sync")
    assert again.returncode == 0, again.stdout + again.stderr
    assert _settings(repo.path, "explorer") == (("gpt-6.1-sol", "high"), ("haiku", "high"))


def test_3_forge_ask_selects_explore_instead_of_lite(repo, monkeypatch, sdk_data):
    folder, log = _codex_repo(repo, monkeypatch, sdk_data)
    toml = folder / "forge.toml"
    toml.write_text(toml.read_text("utf-8").split("\n[", 1)[0] + "\n" + MODELS,
                    encoding="utf-8")
    asked = repo.forge("ask", "Where is the parser?", cwd=folder)
    assert asked.returncode == 0, asked.stdout + asked.stderr
    assert _sent(log, "thread/start")[-1]["config"] == {
        **QUIET, "model": "gpt-6-luna", "model_reasoning_effort": "high"}


def test_4_earlier_adopted_repo_without_explore_keeps_lite_after_upgrade(
        unsynced_up, monkeypatch, sdk_data):
    # Upgrade starts from the text fixture's actual earlier-adoption files, rather than a
    # current sync given an old version string. Codex keeps lite; Claude gets its default.
    up = unsynced_up
    _repo_adopted_on_the_previous_release(up)
    toml = up.folder / "forge.toml"
    before = toml.read_bytes()
    models = tomllib.loads(before.decode("utf-8"))["models"]
    assert "explore" not in models
    synced = up.repo.forge("sync", cwd=up.folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert toml.read_bytes() == before
    assert _settings(up.folder, "explorer") == (
        ("gpt-6.1-sol", "medium"), ("claude-sonnet-5-5", "xhigh"))
    log = _sdk(up.repo, monkeypatch, sdk_data, up.folder)
    asked = up.repo.forge("ask", "Where is the parser?", cwd=up.folder)
    assert asked.returncode == 0, asked.stdout + asked.stderr
    assert _sent(log, "thread/start")[-1]["config"] == {
        **QUIET, "model": "gpt-6.1-sol", "model_reasoning_effort": "medium",
        "agents.default_subagent_model": "gpt-6-luna",
        "agents.default_subagent_reasoning_effort": "max"}


@pytest.mark.parametrize("host", ["codex", "claude"])
def test_5_a_fix_first_build_keeps_lite_with_explore_configured(
        repo, monkeypatch, sdk_data, host, request):
    if host == "codex":
        request.getfixturevalue("claude_session")
    log = _sdk(repo, monkeypatch, sdk_data, repo.path) if host == "codex" else install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             f'workers = "{host}"\ntest = "echo ok"\n{MODELS}')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Choose build and read-only models")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Fix the login typo", "--done", "The login page says Log in")
    assert started.returncode == 0, started.stdout + started.stderr
    built = repo.forge("work", "fix-the-login-typo")
    assert built.returncode == 0, built.stdout + built.stderr
    if host == "codex":
        settings = _sent(log, "thread/start")[0]["config"]
        assert (settings["model"], settings["model_reasoning_effort"]) == ("gpt-6-sol", "low")
    else:
        assert calls(log)[0]["args"][:5] == ["-p", "--model", "sonnet", "--effort", "medium"]
