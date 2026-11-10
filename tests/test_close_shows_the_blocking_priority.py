"""Close shows the priority that keeps a finding open past the round limit."""
import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_two_round_limit import client
from test_worker import install_claude

STORY = "finding-priority-shown-matches"


@pytest.mark.platform
@pytest.mark.parametrize("adopted,scores", [
    (False, "Gain 5, Work 1, Harm 1"),
    (False, "Gain 2, Work 5, Harm 4"),
    (True, "Gain 5, Work 1, Harm 1"),
])
def test_1_close_shows_the_priority_that_blocks_past_the_round_limit(env, adopted, scores):
    client(env, adopted)
    install_claude(env.repo)
    item, where = env.start_fix()
    note = finding("P1", "Saving deletes the basket")
    note["body"] = scores + "\nCase: normal use - Saving deletes the basket."
    env.reviews(blocked(note))

    for number in (1, 2):
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        env.commit(where, "app.py", f"print('repair {number}')\n")
        closed = env.close(item)
        assert closed.returncode == 1, closed.stdout + closed.stderr
        assert "reached the round limit" not in closed.stderr
        assert "1. P0 Saving deletes the basket (app.py:1)\n" in closed.stdout
        published = body((env.gh_calls("pr", "edit") or env.gh_calls("pr", "create"))[-1])
        assert "- Finding 1 (P0): Saving deletes the basket (app.py:1): blocks the merge" in published
        assert "P0 Saving deletes the basket (app.py)" in published
        assert "P1 Saving deletes the basket" not in published

    stopped = env.repo.forge("work", item)
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "Two rounds in a row left the open P0 saving deletes the basket in app.py." in stopped.stderr
