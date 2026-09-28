"""This repo's own workers run on Claude Opus 5.5 at medium effort; reviews stay on Codex."""
from __future__ import annotations

import tomllib

from conftest import ROOT
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
