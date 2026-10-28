"""Land repairs a stale review through close, without a product worker round."""

import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_land import ITEM, RUNS, _fix, _land, _queue, _runs, _workers, land  # noqa: F401
from test_land_checks import LINK, _failing
from test_stacked_fixes_count_only_their_own_changes import configured

STORY = "review-after-replay"


@pytest.mark.parametrize("previous,problem,other_failure,persistent", [
    pytest.param(previous, problem, other_failure, persistent,
                 id=f"{problem}-{other_failure}-{persistent}-{history}")
    for previous, history in [(False, "new"), (True, "previously-adopted")]
    for index, (problem, other_failure, persistent) in enumerate([
        ("missing", False, False),
        ("for a commit that isn't part of this branch", False, False),
        ("out of date: the product files or what the change must do changed after it", False, False),
        ("blocked by serious findings no one fixed or dismissed", False, False),
        ("missing", True, False),
        ("missing", False, True),
    ])
    if not previous or index not in (0, 2)
])
def test_2_land_closes_again_for_its_stale_review_check(land, previous, problem, other_failure, persistent):
    configured(land, previous)
    _fix(land, "working", worked=True)
    red = [run("tests", "failure" if other_failure else "success"), run("forge-pr-check", "failure")]
    _queue(land, RUNS, *_runs(red, red if persistent else GREEN))
    failures = [("forge-pr-check", LINK.format(9),
                 f"The committed review at the head of fix/{ITEM} is {problem}.\n")]
    if other_failure:
        failures.append(("tests", LINK.format(10), "app.py:1: assertion failed\n"))
    _failing(land, *failures)
    done = _land(land)
    assert done.returncode == (1 if persistent else 0), done.stdout + done.stderr
    repairable = not other_failure and problem != "blocked by serious findings no one fixed or dismissed"
    assert len(_workers(land)) == (0 if repairable else 1)
    assert done.stdout.count(f"Closing {ITEM}.") == 2
    if repairable:
        assert "Fix round" not in done.stdout
        assert not land.gh_calls("run", "rerun")
