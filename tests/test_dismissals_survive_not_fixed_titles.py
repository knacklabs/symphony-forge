"""Repair-review titles preserve dismissals only for the same file and unchanged evidence."""

import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "issue-1043-a-dismissed-finding-comes-bac"


@pytest.mark.parametrize("previous, change", [
    (False, "unrelated"), (True, "unrelated"), (False, "cited"), (False, "file"),
], ids=["new", "earlier-adopted", "changed-evidence", "different-file"])
def test_1_not_fixed_keeps_dismissal_only_for_unchanged_evidence_in_the_same_file(env, previous, change):
    client(env, previous)
    item, where = env.start_task(changes={"app.py": "safe = True\n", "other.py": "safe = True\n"})
    original = {**finding("P1", "Saving skips the coupon"),
                "body": "Gain 4, Work 1, Harm 2\nSaving skips the coupon."}
    env.reviews(blocked(original))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    reason = "app.py:1 The coupon is already applied"
    dismissed = env.close(item, "--dismiss", "1", "--because", reason)
    assert dismissed.returncode == 0, dismissed.stdout + dismissed.stderr

    # Only the review title changes in the main case. The other cases guard the
    # file boundary and the rule that a real edit to cited evidence ends a dismissal.
    env.commit(where, "app.py", "safe = False\n" if change == "cited" else "safe = True\nextra = 1\n")
    path = "other.py" if change == "file" else "app.py"
    repeated = {**original, "title": "Not fixed: Saving skips the coupon",
                "code_location": {"file_path": path, "line": 1}}
    env.reviews(blocked(repeated))
    result = env.close(item)
    assert len(env.review_calls()) == 2
    shown = body(env.gh_calls("pr", "edit")[-1])
    if change == "unrelated":
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Ready:" in result.stdout
        assert f"Not fixed: Saving skips the coupon (app.py:1): dismissed because {reason}" in shown
    else:
        assert result.returncode == 1, result.stdout + result.stderr
        assert "One more round, split or accept?" in result.stderr
        assert f"Not fixed: Saving skips the coupon ({path}:1): blocks the merge" in shown
