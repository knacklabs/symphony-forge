"""Close holds approved outcomes with extra title words, but keeps details as advice."""
import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_explains_findings_and_requires_done_when import setup_client

STORY = "not-done-with-added-words"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
@pytest.mark.parametrize("owner_item", [True, False], ids=["approved", "builder-detail"])
def test_1_extended_done_when_title_blocks_but_builder_details_stay_follow_ups(env, adopted, owner_item):
    setup_client(env, adopted)
    owner = "The readme opens with a greeting."
    detail = "The greeting uses a separate formatter"
    item, where = env.start_fix(done_when=owner)
    env.commit(where, "docs/implementation.md", f"# Builder details\n\n{detail}.\n")
    title = f"Not done: {owner if owner_item else detail} does not finish"
    note = finding("P2", title)
    note["body"] = "Gain 2, Work 4, Harm 1\nThe greeting is absent."
    env.reviews(blocked(note))

    closed = env.close(item)

    published = body(env.gh_calls("pr", "edit")[-1])
    if owner_item:
        assert closed.returncode == 1, closed.stdout + closed.stderr
        assert "Review: blocked." in closed.stdout
        assert "Ready:" not in closed.stdout
        assert f"{title} (app.py:1): blocks the merge" in published
        assert "Follow-ups:" not in published
    else:
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert "Review: clean." in closed.stdout
        assert "Follow-ups:" in published and title in published
        assert "blocks the merge" not in published
