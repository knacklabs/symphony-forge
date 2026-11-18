"""Close catches absent or empty proof before review; land carries the refusal.

Audit: the command refusal and absence of a review call protect the preflight
contract. Removing the preflight lets Autoreview run. Existing proof-delivery
coverage only supplies a list. No production-only test seam is needed.
Land's human and agent paths need their own transport witness because an ignored
return value can falsely report readiness after the same close failure.
"""
import pytest

from test_close import env  # noqa: F401
from test_land import _agent, land  # noqa: F401

STORY = "FIX-FULL-BRIEF-AND-PROOF"


@pytest.mark.parametrize("proof", ["", "\n\nProof list:", "\n\nProof list:\n   "])
def test_1_close_names_missing_proof_before_review(env, proof):
    item, where = env.start_fix()
    env.repo.git("commit", "--amend", "-q", "-m", "Commit the coordinator repair" + proof, cwd=where)
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Proof list: missing. Add the full Proof list to the last commit" in closed.stderr
    assert f"forge close {item}" in closed.stderr
    assert env.review_calls() == []
    env.repo.git("commit", "--allow-empty", "-q", "-m", "Record the proof",
                 "-m", "Proof list:\n- The greeting: manual check passed", cwd=where)
    ready = env.close(item)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    assert len(env.review_calls()) == 1


@pytest.mark.parametrize("merge", ["human", "agent"])
def test_4_land_stops_at_missing_proof_without_reporting_ready_or_merging(land, merge):
    env = land
    if merge == "agent":
        _agent(env)
    item, where = env.start_fix()
    env.repo.git("commit", "--amend", "-q", "-m", "Commit without the proof", cwd=where)
    env.repo.git("push", "-q", "origin", f"HEAD:refs/heads/fix/{item}", cwd=where)
    env.open_pr("Why: The greeting needs a repair.\nDone when: The greeting works.")

    done = env.repo.forge("land", item)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "Proof list: missing" in done.stdout + done.stderr
    assert f"forge close {item}" in done.stdout + done.stderr
    assert "is ready" not in done.stdout
    assert f"Merging {item}." not in done.stdout
    assert env.review_calls() == []
    assert env.gh_calls("pr", "merge") == []
