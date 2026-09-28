"""This repo's own workers run on Claude Opus 5.5 at medium effort; reviews stay on Codex."""
from __future__ import annotations

import json
import os
import tomllib

from conftest import ROOT
from test_setup import _autoreview, _executable, _stub_forge
from test_worker import calls, install_claude

STORY = "the-owner-moved-this-repo-s-workers-from"
OPUS = {"model": "claude-opus-5-5", "effort": "medium"}


def test_1_this_repo_works_on_claude_opus_medium_and_reviews_on_codex(repo):
    text = (ROOT / "forge.toml").read_text(encoding="utf-8")
    config = tomllib.loads(text)
    assert config["workers"] == "claude"
    # No subagent keys: the whole table is exactly the model and its effort.
    assert config["models"]["build"] == config["models"]["fix"] == config["models"]["lite"] == OPUS
    assert config["models"]["review"] == {"model": "gpt-6-sol", "effort": "xhigh"}

    log = install_claude(repo)
    repo.write("forge.toml", text)
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Configure Forge")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Move workers to Claude", "--done", "Opus builds it")
    assert started.returncode == 0, started.stderr

    worked = repo.forge("work", "move-workers-to-claude")

    assert worked.returncode == 0, worked.stdout + worked.stderr
    [call] = calls(log)
    assert call["args"][:5] == ["-p", "--model", "claude-opus-5-5", "--effort", "medium"]


def test_2_forge_doctor_passes_on_this_repos_forge_toml(repo, gh, tmp_path, monkeypatch):
    repo.write("forge.toml", (ROOT / "forge.toml").read_text(encoding="utf-8"))
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Configure Forge")
    repo.git("push", "-q", "origin", "main")
    repo.git("checkout", "-q", "-b", "fix/doctor")  # sync refuses on main
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    # The machine's prerequisites, controlled: gh signed in, Autoreview at its pin, a claude
    # program, Codex trusting the project and both UI skills where the Claude worker reads them.
    gh.respond("auth", "status")
    _autoreview(tmp_path, monkeypatch)
    _stub_forge(tmp_path, monkeypatch)
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', "utf-8")
    _executable(repo.bin / "claude", "#!/bin/sh\n")
    if os.name == "nt":
        (repo.bin / "claude.cmd").write_text("@exit /b 0\n", encoding="utf-8")
    for skill in ("impeccable", "emil-design-eng"):
        (home / ".claude" / "skills" / skill).mkdir(parents=True)
        (home / ".claude" / "skills" / skill / "SKILL.md").write_text(f"{skill}\n", "utf-8")

    done = repo.forge("doctor")

    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.startswith("Everything checks out"), done.stdout

