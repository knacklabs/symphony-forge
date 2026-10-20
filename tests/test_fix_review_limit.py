"""A fix finishes its review in one round; a story part still has two.

Only GitHub and Autoreview are faked; close owns the decision and publication.
"""
import pytest

from test_close import blocked, env  # noqa: F401
from test_two_round_limit import client, known, note, published

STORY = "one-round-fixes"


@pytest.mark.parametrize("adopted,priority", [(False, "P1"), (False, "P0"),
                                             (True, "P1")])
def test_1_a_fix_finishes_after_one_review_and_p0_waits_for_the_owner(env, adopted, priority):
    client(env, adopted)
    entry = note(priority, "Saving loses quantities")
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
        assert "--resolve" in closed.stderr and "human" in closed.stderr
    again = env.close(item)
    assert again.returncode == closed.returncode, again.stdout + again.stderr
    if priority == "P0":
        assert "--resolve" in again.stderr
        accepted = env.close(item, "--resolve", "accept", "--reason", "Keep the current save flow")
        assert accepted.returncode == 0 and "Ready" in accepted.stdout, accepted.stdout + accepted.stderr
    assert len(env.review_calls()) == 1
