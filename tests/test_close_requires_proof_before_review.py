"""Close catches an absent proof record before spending a model review.

Audit: the command refusal and absence of a review call protect the preflight
contract. Removing the preflight lets Autoreview run. Existing proof-delivery
coverage only supplies a list. No production-only test seam is needed.
"""
from test_close import env  # noqa: F401

STORY = "FIX-FULL-BRIEF-AND-PROOF"


def test_1_close_names_missing_proof_before_review(env):
    item, where = env.start_fix()
    env.repo.git("commit", "--amend", "-q", "-m", "Commit the coordinator repair", cwd=where)
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Proof list: missing. Add the full Proof list to the last commit, then run" in closed.stderr
    assert f"forge close {item}" in closed.stderr
    assert env.review_calls() == []
    env.repo.git("commit", "--allow-empty", "-q", "-m", "Record the proof",
                 "-m", "Proof list:\n- The greeting: manual check passed", cwd=where)
    ready = env.close(item)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    assert len(env.review_calls()) == 1
