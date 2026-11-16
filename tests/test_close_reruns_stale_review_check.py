STORY = "FIX-REVIEW-CHECK-RACE"
# Close reruns the review check once, when it failed before close posted the updated review.

import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_land import ITEM, RUNS, _fix, _queue, _runs, land  # noqa: F401
from test_land_checks import LINK, _failing
from test_stacked_fixes_count_only_their_own_changes import configured


def test_1_close_reruns_the_review_check_that_saw_the_old_review(land):
    configured(land, False)
    where = _fix(land, "working", worked=True)
    red = [run("tests"), run("forge-pr-check", "failure")]
    _queue(land, RUNS, *_runs(red, GREEN))
    _failing(land, ("forge-pr-check", LINK.format(9),
                    f"The committed review at the head of fix/{ITEM} is out of date: "
                    "the product files or what the change must do changed after it.\n"))
    done = land.repo.forge("close", ITEM, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(land.gh_calls("run", "rerun")) == 1
