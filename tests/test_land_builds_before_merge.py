"""Land builds an amended, unbuilt fix but keeps record-only work valid."""

import sys

import pytest

from conftest import GH_STUB, _install
from test_close import env  # noqa: F401
from test_land import GH, ITEM, URL, _agent, _fix, _land, _workers, land  # noqa: F401
from test_stacked_fixes_count_only_their_own_changes import configured

STORY = "land-builds-before-merge"


@pytest.mark.parametrize("previous,worked", [(False, False), (True, False), (False, True)],
                         ids=["new", "previously-adopted", "record-only-work"])
def test_1_land_builds_unbuilt_fixes_and_accepts_record_only_work(land, previous, worked):
    configured(land, previous)
    _install(land.repo.bin, "gh", GH.format(
        python=sys.executable, remote=land.repo.git("remote", "get-url", "origin"), url=URL)
        + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    _agent(land)
    where = _fix(land)
    if worked:
        land.commit(where, "plans/result.md", "The requested record\n", "Write the requested record")
    amended = land.repo.forge("fix", "amend", ITEM, "--done", "The requested record exists",
                             "--because", "Clarify the result", cwd=where)
    assert amended.returncode == 0, amended.stdout + amended.stderr
    expected = f"Next: forge {'close' if worked else 'work'} {ITEM}"
    next_step = land.repo.forge("next", cwd=where)
    assert next_step.returncode == 0, next_step.stdout + next_step.stderr
    done = _land(land)
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(_workers(land)) == (0 if worked else 1)
    assert len(land.gh_calls("pr", "merge")) == 1
    if worked:
        assert land.repo.git("show", "origin/main:plans/result.md") == "The requested record"
    else:
        assert done.stdout.index(f"Building {ITEM}.") < done.stdout.index(f"Closing {ITEM}.")
        assert land.repo.git("show", "origin/main:work-1.txt") == "worked"
    assert expected in amended.stdout
    assert expected in next_step.stdout
