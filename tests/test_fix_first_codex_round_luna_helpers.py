"""A fix's first Codex round receives the lite kind's helper settings."""
from __future__ import annotations

import json
import os
import tomllib

from conftest import ROOT, _install
from test_codex_worker import _sent, sdk_data  # noqa: F401 (pytest fixture)
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

STORY = "a-fix-s-first-codex-round-runs-as-the-li"
HELPERS = {"agents.default_subagent_model": "gpt-6-luna",
           "agents.default_subagent_reasoning_effort": "max"}


def test_1_forge_init_gives_lite_luna_max_helpers(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)

    initialized = repo.forge("init", cwd=client)

    assert initialized.returncode == 0, initialized.stderr
    lite = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["models"]["lite"]["codex"]
    assert lite["subagents"] == "gpt-6-luna"
    assert lite["subagent_effort"] == "max"


def test_2_first_fix_round_sends_a_codex_repos_lite_helpers(repo, monkeypatch, sdk_data):
    _install(repo.bin, "codex-app-server",
             (ROOT / "tests/stubs/codex-app-server").read_text(encoding="utf-8"))
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    repo.write("forge.toml", (ROOT / "tests/fixtures/codex-forge.toml").read_text(encoding="utf-8"))
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Configure Forge")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Give first fixes helpers", "--done",
                         "The first round receives Luna max helpers")
    assert started.returncode == 0, started.stderr
    fix = repo.path.parent / "repo-fix-give-first-fixes-helpers"
    codex_home = repo.path.parent / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(fix))}]\ntrust_level = "trusted"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    worked = repo.forge("work", "give-first-fixes-helpers")

    assert worked.returncode == 0, worked.stdout + worked.stderr
    calls = repo.bin / "codex-app-server.jsonl"
    [first] = _sent(calls, "thread/start")
    assert {key: first["config"].get(key) for key in HELPERS} == HELPERS
