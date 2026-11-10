"""Close holds approved outcomes despite small wording changes."""
import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_explains_findings_and_requires_done_when import setup_client

STORY = "not-done-fuzzy-match"


@pytest.mark.parametrize("adopted,wording", [
    (False, "The guide lists the commands and worker brief carries them"),
    (False, "THE GUIDE lists commands, and the worker brief carries them!"),
    (False, "The guide lists the commands and the worker brief carries the them"),
    (False, "The worker brief uses a separate formatter"),
    (True, "The guide lists the commands and worker brief carries them"),
], ids=["missing-the", "case-punctuation", "extra-the", "builder-detail", "earlier-adopted"])
def test_1_small_word_changes_block_but_builder_details_stay_follow_ups(env, adopted, wording):
    setup_client(env, adopted)
    item, where = env.start_fix(
        done_when="The guide lists the commands and the worker brief carries them.")
    detail = "The worker brief uses a separate formatter"
    env.commit(where, "docs/implementation.md", f"# Builder details\n\n{detail}.\n")
    note = finding("P2", f"Not done: {wording}")
    note["body"] = "Gain 2, Work 4, Harm 1\nThe promised outcome is absent."
    env.reviews(blocked(note))

    closed = env.close(item)

    published = body(env.gh_calls("pr", "edit")[-1])
    if wording == detail:
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert "Review: clean." in closed.stdout
        assert "Follow-ups:" in published and note["title"] in published
        assert "blocks the merge" not in published
    else:
        assert closed.returncode == 1, closed.stdout + closed.stderr
        assert "Review: blocked." in closed.stdout
        assert "Ready:" not in closed.stdout
        assert f"{note['title']} (app.py:1): blocks the merge" in published
        assert "Follow-ups:" not in published
