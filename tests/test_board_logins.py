"""Board people use loaded records and retain cached identities during outages.

Three command-boundary cases cover a missing CLI, an expired cache during a GitHub
outage, and an actual upgrade of an earlier-adopted client. No Forge internals are
imported and no identity lookup is faked.
"""
from datetime import datetime, timedelta, timezone
import shutil
import sys

import pytest

from conftest import _install
from test_board_counts import board, github, rows
from test_board_trends import pr
from test_board_after_upgrade import History, NOW
from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401
from test_story import worktree

STORY = "FORGE-BOARD-3"


def _remove_gh(env, monkeypatch):
    # Real Git and platform probes remain available; no directory can supply gh.
    isolated = env.tmp / "without-gh"
    isolated.mkdir()
    for command in ("git", "sysctl", "vm_stat"):
        executable = shutil.which(command)
        if executable:
            _install(isolated, command, f"#!{sys.executable}\nimport subprocess, sys\n"
                     f"sys.exit(subprocess.run([{executable!r}, *sys.argv[1:]]).returncode)\n")
    monkeypatch.setenv("PATH", isolated.as_posix())
    assert shutil.which("gh") is None


@pytest.mark.parametrize("case", ["gh-absent", "github-unreachable", "adopted-upgrade"])
def test_1_board_people_keep_loaded_names_and_logins(env, monkeypatch, unsynced_up, case):
    if case == "adopted-upgrade":
        history = History(unsynced_up, monkeypatch)
        history.story()
        plan = (history.repo.path / "plans/SHOP.md").read_text("utf-8")
        history.commit(history.repo.path, "plans/SHOP.md",
                       plan + "\n## For the builders\n\nOwner: plan-owner\n",
                       "Assign the plan owner", NOW - timedelta(days=20))
        history.repo.git("merge", "-q", "--ff-only", "main", cwd=worktree(history.repo, "story/SHOP"))
        history.repo.git("push", "-q", "origin", "story/SHOP")
        history.item("recorded-people", 21, 10)
        history.publish()
        upgraded = unsynced_up.run(RELEASE)
        assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
        env, repo, item = history.env, history.repo, "recorded-people"
        now, author, merger = NOW, "Original Starter", "Human Merger"
        author_login, merger_login = "starter", "merger"
    else:
        client(env, False)
        repo = env.repo
        now = datetime.now(timezone.utc)
        monkeypatch.setenv("FORGE_NOW", now.isoformat())
        repo.git("config", "user.name", "Git Builder")
        repo.git("config", "user.email", "builder@example.test")
        item, _ = env.start_fix()
        repo.git("merge", "-q", "--no-edit", "fix/tidy-readme")
        repo.git("push", "-q", "origin", "main")
        author, author_login = "Git Builder", "builder-dev"
        merger = merger_login = "merge-owner"
        merged = pr(21, "fix/tidy-readme", {"name": author, "login": author_login}, now)
        merged["mergedBy"] = {"login": merger_login}
        github(env, [merged])
    env.gh.respond("api", "user", stdout="viewer-dev\n")
    before = len(env.gh.calls())
    warm = rows(board(repo))[item]  # Populate the real command's last-known records.
    assert warm["started_by_login"] == author_login
    assert warm["merged_by"]["login"] == merger_login

    if case == "github-unreachable":
        env.gh.respond("pr", "list", exit=1, stderr="GitHub is unreachable\n")
        env.gh.respond("api", exit=1, stderr="GitHub is unreachable\n")
    else:
        _remove_gh(env, monkeypatch)

    for seconds in (0, 121):
        monkeypatch.setenv("FORGE_NOW", (now + timedelta(seconds=seconds)).isoformat())
        shown = board(repo)
        person = rows(shown)[item]
        assert (person["started_by"], person["started_by_login"]) == (author, author_login)
        assert person["merged_by"] == {"name": merger, "login": merger_login}
        assert shown["viewer"] == "viewer-dev"
        if case == "adopted-upgrade":
            plan_owner = rows(shown)["SHOP"]
            assert (plan_owner["developer"], plan_owner["developer_login"]) == ("plan-owner", "plan-owner")
    assert not [call for call in env.gh.calls()[before:] if call[:1] == ["api"] and (
        any("object(oid:" in arg for arg in call)
        or any(arg.startswith("repos/{owner}/{repo}/commits/") and "/check-runs" not in arg
               for arg in call))]
