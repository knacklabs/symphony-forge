"""A review loop stopped by land can be resolved through close."""

import pytest

from test_close import CLEAN, STORY_DOC, blocked, env, finding  # noqa: F401
from test_land import _land, _workers, land  # noqa: F401

STORY = "three-rounds-ask"


@pytest.mark.parametrize("choice", ["more", "accept"])
def test_3_land_records_the_humans_review_loop_choice(land, choice):
    ITEM, where = land.start_approved_task(STORY_DOC)
    # Round one gets one repair; a P1 at the bar in round two waits for the owner's choice.
    land.reviews(blocked(finding("P1", "Greeting is missing")),
                 blocked({**finding("P1", "Opening the page loses saved work", "work-1.txt"),
                          "body": "Gain 4, Work 1, Harm 2\nNormal page loads lose saved work."}))
    stopped = _land(land, ITEM)
    assert stopped.returncode == 3, stopped.stdout + stopped.stderr
    assert "Ask the human" in stopped.stderr
    assert f"forge close {ITEM} --resolve <more|split|accept>" in stopped.stderr
    assert len(land.review_calls()) == 2
    workers = len(_workers(land))
    assert workers == 1
    assert not land.gh_calls("pr", "merge")

    # Repeating either entry point cannot run another worker or reviewer until
    # the coordinator records the human's choice.
    for again, code in ((_land(land, ITEM), 3), (land.close(ITEM), 1)):
        assert again.returncode == code, again.stdout + again.stderr
        assert "Ask the human" in again.stderr
    assert len(land.review_calls()) == 2
    assert len(_workers(land)) == workers

    recorded = land.close(ITEM, "--resolve", choice, "--reason", "The human chose this part")
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert "Recorded the human's choice." in recorded.stdout
    assert len(land.review_calls()) == 2
    assert len(_workers(land)) == workers
    if choice == "accept":
        assert f"Ready: {ITEM}" in recorded.stdout
    else:
        assert f"Next: forge work {ITEM}" in recorded.stdout
        land.commit(where, "app.py", "print('greeting')\n", "Make the agreed change")
        land.reviews(CLEAN)
        continued = _land(land, ITEM)
        assert continued.returncode == 0, continued.stdout + continued.stderr
        assert f"{ITEM} is ready; a human merges" in continued.stdout
        assert len(land.review_calls()) == 3
        assert len(_workers(land)) == workers
