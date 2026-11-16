"""A dismissal never covers a later finding of higher scored priority with the same title and file."""

import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "review-findings-split-from-since-7-nov-2"
APP = "".join(f"line{n} = {n}\n" for n in range(1, 21))


@pytest.mark.parametrize("serious", [
    ("P0", "Gain 5, Work 2, Harm 5"),
    ("P1", "Gain 4, Work 2, Harm 4"),  # raw P1 that the Harm floor scores as P0
], ids=["raw-p0", "scored-p0"])
def test_1_dismissed_p1_does_not_settle_a_more_serious_finding_with_the_same_title_and_file(env, serious):
    client(env, False)
    item, where = env.start_task(changes={"app.py": APP})
    demo = {**finding("P1", "Handler skips the check", line=3),
            "body": "Gain 4, Work 1, Harm 2\nThe demo handler skips the check."}
    env.reviews(blocked(demo))
    assert env.close(item).returncode == 1
    reason = "app.py:3 The demo handler is not real"
    assert env.close(item, "--dismiss", "1", "--because", reason).returncode == 0

    # The repair review repeats the demo note with its line moved and adds the serious one.
    env.commit(where, "app.py", "first = 0\n" + APP)
    real = {**finding(serious[0], "Handler skips the check", line=9),
            "body": f"{serious[1]}\nThe payment handler skips the authorization check."}
    env.reviews(blocked({**demo, "code_location": {"file_path": "app.py", "line": 4}}, real))
    result = env.close(item)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "serious findings open: finding 2 (Handler skips the check)" in result.stderr
    shown = body(env.gh_calls("pr", "edit")[-1])
    assert f"Handler skips the check (app.py:4): dismissed because {reason}" in shown
    assert "Handler skips the check (app.py:9): blocks the merge" in shown
