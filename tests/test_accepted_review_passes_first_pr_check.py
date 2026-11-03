"""The first close after acceptance publishes a current review."""

import pytest

from test_close import blocked, env, finding  # noqa: F401
from test_two_round_limit import client

STORY = "accept-review-not-stale"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
def test_1_first_accepted_close_passes_pr_check_on_pushed_head(env, previous):
    client(env, previous)
    env.commit(env.repo.path, "greeting.py", "GREETING = 'Hello'\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.commit(where, "app.py", "print('hello again')\n",
               "Repair greeting\n\nFunctional check: Ran the greeting and saw hello again.")
    defect = finding("P1", "Greeting needs more detail", "greeting.py")
    defect["body"] = "Gain 4, Work 1, Harm 2\nCase: normal use - Readers miss the detail."
    env.reviews(blocked(defect))
    stopped = env.close(item)
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "reached the round limit" in stopped.stderr

    accepted = env.close(item, "--resolve", "accept", "--reason", "Keep this greeting for now")
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "Review: clean." in accepted.stdout
    head = env.repo.git("rev-parse", f"refs/remotes/origin/fix/{item}", cwd=where)
    checked = env.repo.forge("hook", "pr-check", "--base", "origin/main", "--head", head,
                             "--branch", f"fix/{item}", cwd=where)
    assert checked.returncode == 0, checked.stdout + checked.stderr
