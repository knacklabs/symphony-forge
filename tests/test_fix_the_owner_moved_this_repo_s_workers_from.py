"""This repo uses split workers since 18 Nov 2026: Codex for code, Claude for user-facing parts.

Build, fix and lite use low effort; design keeps high. Cold reads and reviews use Terra max.
"""
from __future__ import annotations

import json
import os
import tomllib

from conftest import ROOT, _install
from test_codex_setup import _signed_in_codex
from test_codex_worker import _sent, sdk_data  # noqa: F401 (fixture)
from test_setup import _autoreview, _stub_forge
from test_subagent_roles import _settings
from test_worker import calls, install_claude

import pytest

pytestmark = pytest.mark.platform

STORY = "the-owner-moved-this-repo-s-workers-from"
# Audit: these existing command tests own this repo's model settings and synced
# roles accepted by doctor. The owner changed the worker contract on 2026-11-18;
# retain literal expectations so a model regression cannot validate itself.
# No new test, duplicate boundary coverage or production seam is needed.
SOL = {"model": "gpt-6.1-sol", "effort": "low"}
SONNET = {"model": "claude-sonnet-5-5", "effort": "low"}
CLAUDE_BUILD = {**SONNET, "subagents": "claude-haiku-5-5", "subagent_effort": "high"}


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


def test_1_this_repo_works_on_claude_low_and_reviews_on_codex(repo, monkeypatch, sdk_data):
    text = (ROOT / "forge.toml").read_text(encoding="utf-8")
    config = tomllib.loads(text)
    assert config["workers"] == "split"
    # Both tools start implementation at low effort; split sends code work to Codex.
    assert config["models"]["build"] == config["models"]["fix"] == {
        "codex": SOL, "claude": CLAUDE_BUILD}
    assert config["models"]["lite"] == {
        "codex": {**SOL, "subagents": "gpt-6-luna", "subagent_effort": "max"},
        "claude": CLAUDE_BUILD}
    for kind in ("design", "grill"):
        assert config["models"][kind] == {
            "codex": ({"model": "gpt-6.1-terra", "effort": "max"} if kind == "grill" else
                      {"model": "gpt-6.1-sol", "effort": "high"}),
            "claude": {**SONNET, "effort": "high"}}
    assert config["models"]["review"] == {"model": "gpt-6.1-terra", "effort": "max"}
    assert "stage" not in config and "signoff" not in config

    claude_log = install_claude(repo)
    log = _codex(repo, monkeypatch, sdk_data)
    repo.write("forge.toml", text)
    repo.git("add", "forge.toml")
    repo.git("commit", "--allow-empty", "-q", "-m", "Configure Forge")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Move code work to Codex", "--done", "Codex builds it")
    assert started.returncode == 0, started.stderr

    worked = repo.forge("work", "move-code-work-to-codex")

    assert worked.returncode == 0, worked.stdout + worked.stderr
    # A fix's first turn uses lite, which this repo sets to Sol at low effort.
    [start] = _sent(log, "thread/start")
    assert (start["config"]["model"], start["config"]["model_reasoning_effort"]) == (
        "gpt-6.1-sol", "low")
    assert len(_sent(log, "turn/start")) == 1
    assert calls(claude_log) == []


def test_2_forge_doctor_passes_on_this_repos_forge_toml(repo, gh, tmp_path, monkeypatch,
                                                   sdk_data):
    _signed_in_codex(repo)
    repo.write("forge.toml", (ROOT / "forge.toml").read_text(encoding="utf-8"))
    repo.git("add", "forge.toml")
    repo.git("commit", "--allow-empty", "-q", "-m", "Configure Forge")
    repo.git("push", "-q", "origin", "main")
    repo.git("checkout", "-q", "-b", "fix/doctor")  # sync refuses on main
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    # Hands-on Codex roles now use lite's subagent budget when build has no pair.
    # Claude keeps its own nested model entry; sync must not drop either host's routing.
    for name in ("worker", "fixer", "coder", "frontend", "tester", "refactorer"):
        assert _settings(repo.path, name) == (
            ("gpt-6-luna", "max"),
            ("claude-sonnet-5-5", "high" if name == "frontend" else "low")), name
    # Explorer uses read-only explore settings; implementation roles use Sonnet.
    assert _settings(repo.path, "explorer") == (
        ("gpt-6.1-sol", "medium"), ("claude-haiku-5-5", "high"))
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
    # This repo uses Codex for code and reviews, so doctor names the Codex hook approval.
    assert "approve Forge's hooks" in done.stdout
