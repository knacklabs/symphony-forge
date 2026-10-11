"""A review loop stopped by land can be resolved through close."""

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_land import ITEM, _fix, _land, _workers, land  # noqa: F401

STORY = "three-rounds-ask"


@pytest.mark.parametrize("choice", ["narrow", "split", "accept"])
def test_3_land_records_the_humans_review_loop_choice(land, choice):
    # Different files avoid the existing same-file stop, so this exercises the
    # three-consecutive-blocked-round hold and its land-to-close handoff.
    where = _fix(land, "working", worked=True, changes={
        "app.py": "print('hello')\n", "other.py": "print('hello')\n",
        "show.py": "print('hello')\n",
    })
    land.reviews(*(blocked(finding("P1", "Greeting is missing", file=file))
                   for file in ("app.py", "other.py", "show.py")))
    stopped = _land(land)
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "Ask the human" in stopped.stderr
    assert f"forge close {ITEM} --resolve <narrow|split|accept>" in stopped.stderr
    assert len(land.review_calls()) == 3
    workers = len(_workers(land))
    assert workers == 3
    assert not land.gh_calls("pr", "merge")

    # Repeating either entry point cannot run another worker or reviewer until
    # the coordinator records the human's choice.
    for again in (_land(land), land.close(ITEM)):
        assert again.returncode == 1, again.stdout + again.stderr
        assert "Ask the human" in again.stderr
    assert len(land.review_calls()) == 3
    assert len(_workers(land)) == workers

    recorded = land.close(ITEM, "--resolve", choice, "--reason", "The human chose this part")
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert "Recorded the human's choice." in recorded.stdout
    assert len(land.review_calls()) == 3
    assert len(_workers(land)) == workers
    if choice == "accept":
        assert f"Ready: {ITEM}" in recorded.stdout
    else:
        assert f"{choice.capitalize()} the part as agreed" in recorded.stdout
        land.commit(where, "app.py", "print('greeting')\n", "Make the agreed change")
        land.reviews(CLEAN)
        continued = _land(land)
        assert continued.returncode == 0, continued.stdout + continued.stderr
        assert f"{ITEM} is ready; a human merges" in continued.stdout
        assert len(land.review_calls()) == 4
        assert len(_workers(land)) == workers
