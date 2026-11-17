"""A fix whose only change is a carried idea in plans/ideas.md is not built work."""
import sys

from conftest import _install, GH_STUB
from test_close import env  # noqa: F401
from test_land import GH, ITEM, URL, _agent, _fix, _land, _workers, land  # noqa: F401
from test_stacked_fixes_count_only_their_own_changes import configured

STORY = "FIX-IDEA-ONLY-UNBUILT"


def test_1_a_fix_that_only_carries_an_idea_is_built_before_it_merges(land):
    configured(land, False)
    _install(land.repo.bin, "gh", GH.format(
        python=sys.executable, remote=land.repo.git("remote", "get-url", "origin"), url=URL)
        + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    _agent(land)
    where = _fix(land)
    land.commit(where, "plans/ideas.md", "- 2026-11-17: dark mode\n", "Add ideas for later")

    done = _land(land)

    assert done.returncode == 0, done.stdout + done.stderr
    assert len(_workers(land)) == 1
    assert done.stdout.index(f"Building {ITEM}.") < done.stdout.index(f"Closing {ITEM}.")
    assert len(land.gh_calls("pr", "merge")) == 1


def test_2_close_refuses_a_fix_that_only_carries_an_idea(land):
    configured(land, False)
    where = _fix(land, "working")
    land.commit(where, "plans/ideas.md", "- 2026-11-17: dark mode\n", "Add ideas for later")

    done = land.repo.forge("close", ITEM, cwd=where)

    assert done.returncode != 0, done.stdout + done.stderr
    assert "The build round did not finish." in done.stderr
    assert f"forge work {ITEM}" in done.stderr
    assert not land.gh_calls("pr", "merge")
