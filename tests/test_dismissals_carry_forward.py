"""A dismissed finding stays dismissed while the code its reason cites is unchanged.

Runs the real close command on a repo made by forge init and on the earlier-release adopted
fixture moved to this release. Only Autoreview, GitHub and CI are stubbed.
"""
import pytest

from test_close import blocked, body, env, finding  # noqa: F401 (env is a fixture)
from test_score_bar import CASES, _client_on_this_release

STORY = "FIX-DISMISSALS-CARRY-FORWARD"
APP = "".join(f"line{n} = {n}\n" for n in range(1, 21))


@pytest.mark.parametrize("case", CASES)
def test_1_dismissal_holds_until_its_cited_lines_change(env, tmp_path, case):
    _client_on_this_release(env, tmp_path, case)
    item, where = env.start_fix({"app.py": APP})
    coupon = finding("P1", "Saving skips the coupon", line=3)
    env.reviews(blocked(coupon))
    assert env.close(item).returncode == 1
    reason = "app.py:3 the coupon is applied at checkout"
    dismissed = env.close(item, "--dismiss", "1", "--because", reason)
    assert dismissed.returncode == 0, dismissed.stdout + dismissed.stderr

    # A new commit that moves the cited line and edits its neighbours: still dismissed.
    env.commit(where, "app.py", "first = 0\n" + APP.replace("line2 = 2", "line2 = 0").replace("line4 = 4", "line4 = 0"))
    env.reviews(blocked(coupon))
    ready = env.close(item)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    assert "Ready:" in ready.stdout
    assert f"Saving skips the coupon (app.py:3): dismissed because {reason}" in body(
        env.gh_calls("pr", "edit")[-1])

    # A commit that changes the cited line, with its old text still elsewhere: it blocks again.
    changed = APP.replace("line3 = 3", "line3 = 0") + "line3 = 3\n"
    env.commit(where, "app.py", changed)
    env.reviews(blocked(coupon))
    again = env.close(item)
    assert again.returncode == 1, again.stdout + again.stderr
    assert "Saving skips the coupon" in again.stderr

    # Dismissed again with the same reason: it holds on later commits that leave the new line alone.
    redismissed = env.close(item, "--dismiss", "1", "--because", reason)
    assert redismissed.returncode == 0, redismissed.stdout + redismissed.stderr
    env.commit(where, "app.py", changed + "line21 = 21\n")
    env.reviews(blocked(coupon))
    held = env.close(item)
    assert held.returncode == 0, held.stdout + held.stderr
    assert "Ready:" in held.stdout
