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
        # Python joins the React starter only when the owner asks for a Python backend.
        assert ("Use `forge init --starter` for a new React app, and `forge init --starter python` "
                "for a new app whose owner asks for a Python backend.") in skill, host
        assert "Use `forge init` for any other stack, then propose a `fast_test`" in skill, host
        # The constitution interview is the first adoption step; fast-test setup now comes ninth.
        assert ("9. Propose a `fast_test` for the repo: its own test command, keeping its "
                "configuration and setup") in skill, host
        assert "Forge writes no `fast_test` by itself." in skill, host
        assert "pytest" in skill and "forge test --pytest {base}" in skill, host
