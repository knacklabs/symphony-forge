"""An allowance releases a part's size stop without another worker round."""
import pytest

from test_close import STORY_DOC, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "after-the-owner-allows-a-story-part-past"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_allowed_part_closes_after_the_size_question(env, previous):
    # Audit: existing size coverage allows the part before close ever stops it.
    # Only external review and GitHub are fake; the real commands decide whether to stop.
    client(env, previous)
    item, where = env.start_approved_task(STORY_DOC, changes={"app.py": "value = 1\n" * 401})
    stopped = env.close(item)
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "over its limit of 400" in stopped.stderr
    assert not env.review_calls()

    allowed = env.repo.forge("fix", "allow-large", "One indivisible application change", cwd=where)
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr

    # The allowance itself answers the size question. No --resolve or worker round is needed.
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 1
    assert len(env.gh_calls("pr", "create")) == 1
    assert "Recorded allowance: One indivisible application change" in env.prompt()
