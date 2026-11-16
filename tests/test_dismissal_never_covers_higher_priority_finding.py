"""A dismissal never covers a later finding of higher priority with the same title and file."""

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "review-findings-split-from-since-7-nov-2"


def test_1_dismissed_p1_does_not_settle_a_p0_with_the_same_title_and_file(env):
    client(env, False)
    item, where = env.start_task(changes={"app.py": "safe = True\n"})
    demo = {**finding("P1", "Handler skips the check"),
            "body": "Gain 4, Work 1, Harm 2\nThe demo handler skips the check."}
    env.reviews(blocked(demo))
    assert env.close(item).returncode == 1
    reason = "app.py:1 The demo handler is not real"
    assert env.close(item, "--dismiss", "1", "--because", reason).returncode == 0

    env.commit(where, "app.py", "safe = True\nextra = 1\n")
    real = {**finding("P0", "Handler skips the check"),
            "body": "Gain 5, Work 2, Harm 5\nThe payment handler skips the authorization check."}
    env.reviews(blocked(real))
    result = env.close(item)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "dismissed because" not in body(env.gh_calls("pr", "edit")[-1])
