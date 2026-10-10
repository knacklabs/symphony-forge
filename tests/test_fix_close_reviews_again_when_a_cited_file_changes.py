"""forge close reviews the new head when a commit changes a file the earlier review's findings
cite, even a file under plans/ that the review fingerprint otherwise leaves out."""
from __future__ import annotations

from test_close import CLEAN, blocked, env, finding  # noqa: F401

STORY = "FIX-CLOSE-REUSES-AN-EARLIER-REVIEW-AFTER-A-N"


def test_1_close_reviews_again_after_a_commit_changes_a_file_a_finding_cites(env):
    item, where = env.start_fix()
    env.commit(where, "plans/roadmap.json", '{"items": [{"key": "SHOP", "title": "Old"}]}\n')
    env.reviews(blocked(finding("P1", "Roadmap names the wrong title", "plans/roadmap.json")), CLEAN)
    first = env.close(item)
    assert first.returncode != 0
    assert "Roadmap names the wrong title" in first.stdout + first.stderr
    env.commit(where, "plans/roadmap.json", '{"items": [{"key": "SHOP", "title": "New"}]}\n')
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 2
    assert "Roadmap names the wrong title" not in closed.stdout
