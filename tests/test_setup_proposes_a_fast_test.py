"""At forge init and adoption the synced skill tells the coordinating agent to propose a
fast_test from the repo's own test command; Forge writes none itself."""
from __future__ import annotations

import tomllib

from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

STORY = "FIX-REPOS-ONLY-GET-CHANGE-BASED-TEST-RUNS-AT"


def test_1_the_synced_skill_carries_the_fast_test_setup_step(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    result = repo.forge("init", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "fast_test" not in tomllib.loads((client / "forge.toml").read_text("utf-8"))
    for host in (".claude", ".codex"):
        skill = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "`forge init`, then propose a `fast_test`" in skill, host
        assert ("8. Propose a `fast_test` for the repo: its own test command, keeping its "
                "configuration and setup") in skill, host
        assert "Forge writes no `fast_test` by itself." in skill, host
