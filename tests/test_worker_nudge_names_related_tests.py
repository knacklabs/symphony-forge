"""A worker asked to commit is told to run the change's related tests: forge.toml's fast_test with
{base} as the merge base with the default branch, not the whole suite CI runs."""
from __future__ import annotations

from test_fix_claude_workers_start_a_fresh_session_eve import FIX
from test_worker import calls, install_claude

STORY = "every-worker-round-runs-the-repo-s-whole"


def test_1_the_commit_nudge_names_the_fast_test_with_its_base(repo, monkeypatch):
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             'workers = "claude"\ntest = "pytest -q"\n'
                             'fast_test = "pytest -q --since {base}"\n'
                             'models.lite = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin Forge")
    repo.git("push", "-q", "origin", "main")
    base = repo.git("rev-parse", "HEAD")
    assert repo.forge("fix", "start", "Fix the login typo", "--done",
                      "The login page says Log in").returncode == 0
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "login.txt")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "2")

    built = repo.forge("work", FIX)

    assert built.returncode == 0, built.stdout + built.stderr
    nudged = calls(log)[1]
    assert f"Run the change's related tests (`pytest -q --since {base}`)" in nudged["brief"]
