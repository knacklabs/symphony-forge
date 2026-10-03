"""This repo's own workers run on Codex at medium effort; reviews stay on Codex."""
from __future__ import annotations

import json
import os
import tomllib

from conftest import ROOT, _install
from test_codex_worker import _sent, sdk_data  # noqa: F401 (fixture)
from test_setup import _autoreview, _stub_forge
from test_subagent_roles import _settings

STORY = "the-owner-moved-this-repo-s-workers-from"
SOL = {"model": "gpt-6.1-sol", "effort": "medium"}
OPUS = {"model": "claude-opus-5-5", "effort": "medium"}


def _codex(repo, monkeypatch, sdk_data):
    _install(repo.bin, "codex-app-server",
             (ROOT / "tests/stubs/codex-app-server").read_text(encoding="utf-8"))
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    codex_home = repo.path.parent / "codex-home"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', "utf-8")
    return repo.bin / "codex-app-server.jsonl"


def test_1_this_repo_works_on_codex_medium_and_reviews_on_codex(repo, monkeypatch, sdk_data):
    text = (ROOT / "forge.toml").read_text(encoding="utf-8")
    config = tomllib.loads(text)
    assert config["workers"] == "codex"
    # Codex builds and fixes; each Claude entry preserves the previous Opus settings.
    assert config["models"]["build"] == config["models"]["fix"] == {
        "codex": SOL, "claude": OPUS}
    assert config["models"]["lite"] == {
        "codex": {**SOL, "subagents": "gpt-6-luna", "subagent_effort": "max"},
        "claude": OPUS}
    assert config["models"]["review"] == {"model": "gpt-6.1-sol", "effort": "high"}

    log = _codex(repo, monkeypatch, sdk_data)
    repo.write("forge.toml", text)
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Configure Forge")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Move workers to Codex", "--done", "Codex builds it")
    assert started.returncode == 0, started.stderr

    worked = repo.forge("work", "move-workers-to-codex")

    assert worked.returncode == 0, worked.stdout + worked.stderr
    [call] = _sent(log, "thread/start")
    # A fix's first turn uses lite; its helpers must reach the SDK too.
    assert call["config"] == {
        "model": "gpt-6.1-sol", "model_reasoning_effort": "medium",
        "agents.default_subagent_model": "gpt-6-luna",
        "agents.default_subagent_reasoning_effort": "max"}


def test_2_forge_doctor_passes_on_this_repos_forge_toml(repo, gh, tmp_path, monkeypatch,
                                                   sdk_data):
    repo.write("forge.toml", (ROOT / "forge.toml").read_text(encoding="utf-8"))
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Configure Forge")
    repo.git("push", "-q", "origin", "main")
    repo.git("checkout", "-q", "-b", "fix/doctor")  # sync refuses on main
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    # A sync that silently drops both nested entries must not make doctor appear healthy.
    for name in ("worker", "coder", "frontend", "tester", "refactorer", "explorer"):
        assert _settings(repo.path, name) == (
            ("gpt-6.1-sol", "medium"), ("claude-opus-5-5", "medium")), name
    # Codex replaces the Claude executable and UI skills prerequisites with the pinned SDK.
    gh.respond("auth", "status")
    _autoreview(tmp_path, monkeypatch)
    _stub_forge(tmp_path, monkeypatch)
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    _codex(repo, monkeypatch, sdk_data)

    done = repo.forge("doctor")

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Everything checks out for Forge " in done.stdout, done.stdout
    assert "when Codex asks you to approve Forge's hooks, approve them" in done.stdout
