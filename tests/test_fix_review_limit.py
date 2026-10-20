"""A fix finishes its review in one round; a story part still has two.

Only GitHub and Autoreview are faked; close owns the decision and publication.
"""
from datetime import datetime, timedelta, timezone

import pytest

from test_close import blocked, env  # noqa: F401
from test_two_round_limit import client, known, note, published

STORY = "one-round-fixes"


@pytest.mark.parametrize("adopted,priority", [(False, "P1"), (False, "P0"),
                                             (False, "P0-low-harm"),
                                             (True, "P1")])
def test_1_a_fix_finishes_after_one_review_and_p0_waits_for_the_owner(env, monkeypatch, adopted, priority):
    client(env, adopted)
    entry = note(priority.split("-", 1)[0], "Saving loses quantities")
    if priority == "P0-low-harm":
        entry["body"] = "Gain 5, Work 1, Harm 1\nCase: normal use - Saving loses quantities."
    env.reviews(blocked(entry))
    item, where = env.start_fix()
    closed = env.close(item)
    # Previously every fix needed a repair and another review for a P1.
    # Now non-P0 findings are visible follow-ups after the first review.
    if priority == "P1":
        assert closed.returncode == 0 and "Ready" in closed.stdout, closed.stdout + closed.stderr
        assert entry["title"] in published(env).split("Follow-ups:", 1)[1]
        assert known(env, where)[entry["title"]]["reason"] == "Left open after round one"
    else:
        assert closed.returncode == 1 and entry["title"] in closed.stderr, closed.stdout + closed.stderr
        assert "This fix's review found an open P0." in closed.stderr
        assert "--resolve" in closed.stderr and "human" in closed.stderr
        if priority == "P0-low-harm":
            monkeypatch.setenv("FORGE_NOW", (datetime.now(timezone.utc) + timedelta(minutes=31)).isoformat())
            shown = env.repo.forge("next")
            assert shown.returncode == 0 and "--resolve" in shown.stdout, shown.stdout + shown.stderr
            assert "its review found an open P0" in shown.stdout
            assert "Nobody answered" not in shown.stdout
    again = env.close(item)
    assert again.returncode == closed.returncode, again.stdout + again.stderr
    if priority.startswith("P0"):
        assert "--resolve" in again.stderr
        held = env.repo.forge("land", item)
        assert held.returncode == 3 and "--resolve" in held.stderr, held.stdout + held.stderr
        accepted = env.close(item, "--resolve", "accept", "--reason", "Keep the current save flow")
        assert accepted.returncode == 0 and "Ready" in accepted.stdout, accepted.stdout + accepted.stderr
    assert len(env.review_calls()) == 1
