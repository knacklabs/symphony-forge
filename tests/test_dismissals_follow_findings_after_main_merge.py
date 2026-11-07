"""Dismissals survive clean merges and follow renumbered findings when review is needed.

Test-audit: these existing command cases own saved and pending dismissals. The old
contract reviewed every changed branch diff again. The approved contract retains a
clean review after a clean merge, while a pending dismissal still follows the same
finding in a new review. Keep both histories and repeat-close checks, with no seam.
"""

import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "dismiss-after-merge"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
@pytest.mark.parametrize("saved", [False, True], ids=["pending", "recorded"])
def test_1_dismissal_follows_the_same_finding_after_main_merge(env, previous, saved):
    client(env, previous)
    base = "old\n" + "pass\n" * 20 + "tail\n"
    env.commit(env.repo.path, "app.py", base)
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_task(changes={"app.py": base.replace("old", "new").replace("tail", "branch")})
    safe = finding("P1", "Already safe", line=22)
    env.reviews(blocked(safe))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    dismissal = ("--dismiss", "1", "--because", "app.py:22 The branch already handles this")
    if saved:
        result = env.close(item, *dismissal)
        assert result.returncode == 0, result.stdout + result.stderr

    # Main absorbs part of the branch's diff, leaving the cited evidence intact.
    moved = env.commit(env.repo.path, "app.py", base.replace("old", "new"))
    env.repo.git("push", "-q", "origin", "main")
    env.repo.git("fetch", "-q", "origin", cwd=where)
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    env.repo.git("merge-base", "--is-ancestor", moved, "HEAD", cwd=where)
    # A saved dismissal keeps its clean review. Otherwise a different finding takes the old
    # number, and only the matching title and file may be dismissed in the new review.
    env.reviews(blocked(finding("P2", "Optional cleanup"), safe))
    result = env.close(item, *(() if saved else dismissal))
    assert result.returncode == 0, result.stdout + result.stderr
    reviews = 1 if saved else 2
    assert len(env.review_calls()) == reviews
    shown = body(env.gh_calls("pr", "edit")[-1])
    number = 1 if saved else 2
    assert f"Finding {number} (P1): Already safe (app.py:22): dismissed because app.py:22" in shown
    assert "Finding 1 (P2): Optional cleanup (app.py:1): dismissed" not in shown
    if saved:
        assert "Optional cleanup" not in shown
    again = env.close(item)
    assert again.returncode == 0, again.stdout + again.stderr
    assert len(env.review_calls()) == reviews
