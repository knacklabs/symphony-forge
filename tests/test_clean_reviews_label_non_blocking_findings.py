"""Clean close output identifies every printed finding as a non-blocking follow-up."""
import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "clean-review-labels"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_clean_review_labels_non_blocking_p1_findings(env, adopted):
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    client(env, adopted)
    env.commit(env.repo.path, "forge.toml", config, "Use the test checks")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    detail = "Not done: The greeting uses a separate formatter"
    advice = "Simpler: shorten the greeting"
    env.reviews(blocked(finding("P1", detail), finding("P2", advice)))

    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Review: clean.\n" in closed.stdout
    heading = "Follow-ups that do not block the merge (recorded in the pull request):\n"
    before, follow_ups = closed.stdout.split(heading, 1)
    assert detail not in before and advice not in before
    assert f"1. {detail} (app.py:1)" in follow_ups
    assert f"2. {advice} (app.py:1)" in follow_ups
    assert "P1" not in follow_ups
    recorded = body(env.gh_calls("pr", "edit")[-1])
    assert "Follow-ups:" in recorded and detail in recorded and advice in recorded
