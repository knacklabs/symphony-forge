"""A line-ending change preserves dismissal evidence; a change to its text does not."""

import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "windows-accept-body"


@pytest.mark.platform
@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
def test_1_dismissed_findings_keep_their_evidence_after_line_ending_changes(env, previous):
    client(env, previous)
    env.repo.git("config", "core.autocrlf", "false")
    item, where = env.start_task()
    env.commit(where, "src/a.py", "pass\r\n")
    # A P1 at the bar stops for the owner when the cited text changes in a later round.
    safe = {**finding("P1", "Already proved safe", "src/a.py"),
            "body": "Gain 4, Work 1, Harm 2\nEvidence for: Already proved safe"}
    env.reviews(blocked(safe))
    assert env.close(item).returncode == 1
    reason = "src/a.py:1 Proven safe"
    assert env.close(item, "--dismiss", "1", "--because", reason).returncode == 0

    # The cited text is intact when a Windows file becomes LF and gains another line.
    env.commit(where, "src/a.py", "pass\nprint('new work')\n")
    result = env.close(item)
    assert result.returncode == 0, result.stdout + result.stderr
    shown = body(env.gh_calls("pr", "edit")[-1])
    assert f"Already proved safe (src/a.py:1): dismissed because {reason}" in shown

    # A real edit to the cited text still reopens the finding.
    env.commit(where, "src/a.py", "raise RuntimeError('changed')\nprint('new work')\n")
    result = env.close(item)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "reached the round limit with open findings" in result.stderr
    assert "One more round, split or accept?" in result.stderr
    shown = body(env.gh_calls("pr", "edit")[-1])
    assert "Already proved safe (src/a.py:1): blocks the merge" in shown
