"""A review loop stopped by land can be resolved through close."""

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_land import ITEM, _fix, _land, _workers, land  # noqa: F401

STORY = "three-rounds-ask"


@pytest.mark.parametrize("choice", ["narrow", "split", "accept"])
def test_3_land_records_the_humans_review_loop_choice(land, choice):
    # With the default on, land waits out the stop; this checks the owner's own choice.
    toml = land.repo.path / "forge.toml"
    land.commit(land.repo.path, "forge.toml", toml.read_text("utf-8") + 'stop_default = "off"\n')
    land.repo.git("push", "-q", "origin", "main")
    # Different files avoid the existing same-file stop, so this exercises the
    # three-consecutive-blocked-round hold and its land-to-close handoff.
    where = _fix(land, "working", worked=True, changes={
        "app.py": "print('hello')\n", "other.py": "print('hello')\n",
        "show.py": "print('hello')\n",
    })
    # Harm 3 keeps the three-round hold under the bar; new Harm 1 findings would go on to a fourth round.
    land.reviews(*(blocked({**finding("P1", "Greeting is missing", file=file),
                            "body": "Gain 3, Work 2, Harm 3\nEvidence"})
                   for file in ("app.py", "other.py", "show.py")))
    asked = _land(land)
    assert asked.returncode == 1 and "ask the owner" in asked.stderr
    assert len(land.review_calls()) == 2
    # The coordinator records the owner's rule, then sends the focused third round.
    land.commit(where, "README.md", "The owner requires a greeting on every page.\n", "Record the owner's rule")
    focused = land.repo.forge("work", ITEM)
    assert focused.returncode == 0, focused.stdout + focused.stderr
    assert land.close(ITEM).returncode == 1
    assert land.repo.forge("work", ITEM).returncode == 0
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
