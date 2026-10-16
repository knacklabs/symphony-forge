"""Unrelated documentation repairs cannot answer an item's owner question.

The real next command must keep the question after two blocked reviews, even
when a worker commits Markdown that the old broad documentation check accepted.
"""
import pytest

from test_close import blocked, env, finding  # noqa: F401
from test_reviews_converge_on_changed_lines import client, synced
from test_shortplan_briefs import NEW

STORY = "no-wasted-rounds"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
@pytest.mark.parametrize("kind", ["fix", "task"])
def test_5_documentation_outside_the_items_plan_keeps_the_owner_question(env, adopted, kind):
    client(env, adopted)
    item, where = env.start_approved_task(NEW) if kind == "task" else env.start_fix()
    synced(env, where)
    titles = ("Saving drops quantities", "Saving drops discounts")
    for number, title in enumerate(titles, 1):
        env.commit(where, "app.py", f"print('saving repair {number}')\n")
        env.reviews(blocked(finding("P1", title)))
        closed = env.close(item)
        assert closed.returncode == 1 and title in closed.stderr, closed.stdout + closed.stderr

    question = "Stop sending rounds and ask the owner to settle the missing rule."
    for path in (None, "docs/implementation.md", "README.md", "plans/OTHER.md"):
        if path:
            env.commit(where, path, "# Saving\n\nSave every basket line.\n", "Repair saving documentation")
        shown = env.repo.forge("next")
        assert shown.returncode == 0, shown.stdout + shown.stderr
        assert question in shown.stdout, shown.stdout
        assert all(title in shown.stdout for title in titles), shown.stdout
        assert f"Next: forge work {item}" not in shown.stdout, shown.stdout
        assert len(env.review_calls()) == 2
    for host in (".codex", ".claude"):
        guide = " ".join((where / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert ("For a review's second-round question, commit the answer in the item's own plan"
                in guide), host
