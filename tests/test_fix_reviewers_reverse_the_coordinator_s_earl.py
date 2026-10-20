"""The next review's brief carries the coordinator's earlier rulings and dismissals, with their
reasons, so a reviewer raises them again only with new evidence."""
from __future__ import annotations

from test_close import CLEAN, blocked, env, finding  # noqa: F401 (env is a fixture)

STORY = "reviewers-reverse-the-coordinator-s-earl"
RULING = "Ruling: greet in English only - the Done-when names no other language"
DISMISSED = "app.py:1 the greeting is here"


def test_1_rulings_and_dismissals_reach_the_second_review(env):
    item, where = env.start_task()
    env.reviews(blocked(finding("P1", "Greeting is missing")),
                # Only P0s remain blocked in round two and need an explicit dismissal.
                blocked(finding("P0", "Saving corrupts the basket")), CLEAN)
    assert env.close(item).returncode == 1
    assert env.close(item, "--dismiss", "1", "--because", DISMISSED).returncode == 0
    env.commit(where, "app.py", "print('hello again')\n",
               message=f"Say hello again\n\n{RULING}\n")
    assert env.close(item).returncode == 1
    prompt = env.prompt()
    assert RULING in prompt
    assert f"Greeting is missing (app.py): dismissed because {DISMISSED}" in prompt
    assert "only with new evidence" in prompt

    # The P0 stops round two. A recorded extra round permits its evidence dismissal.
    chosen = env.close(item, "--resolve", "more", "--reason", "Check the basket evidence")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    # The third review's findings don't repeat the dismissed one; its reason still reaches it.
    assert env.close(item, "--dismiss", "1", "--because", "app.py:1 The basket is intact").returncode == 0
    env.commit(where, "app.py", "print('hello once more')\n")
    assert env.close(item).returncode == 0
    prompt = env.prompt()
    assert RULING in prompt
    assert f"Greeting is missing (app.py): dismissed because {DISMISSED}" in prompt
    assert "Saving corrupts the basket (app.py): dismissed because app.py:1 The basket is intact" in prompt
