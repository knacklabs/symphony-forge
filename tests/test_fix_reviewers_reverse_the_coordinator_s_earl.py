"""The next review's brief carries the coordinator's earlier rulings and dismissals, with their
reasons, so a reviewer raises them again only with new evidence."""
from __future__ import annotations

from test_close import CLEAN, blocked, env, finding  # noqa: F401 (env is a fixture)

STORY = "reviewers-reverse-the-coordinator-s-earl"
RULING = "Ruling: greet in English only - the Done-when names no other language"
DISMISSED = "app.py:1 the greeting is here"


def test_1_rulings_and_dismissals_reach_the_second_review(env):
    item, where = env.start_fix()
    env.reviews(blocked(finding("P1", "Greeting is missing")),
                blocked(finding("P1", "Greeting should be translated")), CLEAN)
    assert env.close(item).returncode == 1
    assert env.close(item, "--dismiss", "1", "--because", DISMISSED).returncode == 0
    env.commit(where, "app.py", "print('hello again')\n",
               message=f"Say hello again\n\n{RULING}\n")
    assert env.close(item).returncode == 1
    prompt = env.prompt()
    assert RULING in prompt
    assert f"Greeting is missing (app.py): dismissed because {DISMISSED}" in prompt
    assert "only with new evidence" in prompt

    # The third review's findings don't repeat the dismissed one; its reason still reaches it.
    assert env.close(item, "--dismiss", "1", "--because", "app.py:1 English only").returncode == 0
    env.commit(where, "app.py", "print('hello once more')\n")
    assert env.close(item).returncode == 0
    prompt = env.prompt()
    assert RULING in prompt
    assert f"Greeting is missing (app.py): dismissed because {DISMISSED}" in prompt
    assert "Greeting should be translated (app.py): dismissed because app.py:1 English only" in prompt
