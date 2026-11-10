"""Every Not-done holds a fix; story tasks keep their approved-item boundary."""
import subprocess
import sys

import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_explains_findings_and_requires_done_when import earlier_close_command, setup_client
from test_shortplan_briefs import NEW

STORY = "not-done-fuzzy-match"


@pytest.mark.parametrize("adopted,kind,owner,wording,blocks", [
    (False, "fix", "The guide lists the commands and the worker brief carries them.",
     "The guide lists the commands and worker brief carries them", True),
    (False, "fix", "The guide lists the commands and the worker brief carries them.",
     "THE GUIDE lists commands, and the worker brief carries them!", True),
    (False, "fix", "The guide lists the commands and the worker brief carries them.",
     "The guide lists the commands and the worker brief also carries them", True),
    (False, "fix", "The e-mail is sent to users.", "The email is sent to users", True),
    (False, "fix", "The guide lists the commands and the worker brief carries them.",
     "The worker brief uses a separate formatter", True),
    (True, "fix", "The guide lists the commands and the worker brief carries them.",
     "The guide lists the commands and worker brief carries them", True),
    (False, "task", "A shopper can save a basket.", "The worker brief uses a separate formatter", False),
    (False, "task", "The form shows the name of the owner.",
     "The form shows the name to the owner in bold", False),
    (False, "task", "Build a C++ client.", "Build a C client", False),
    (False, "task", "A shopper can save a basket.", "A shopper can save a basket. but it fails", True),
], ids=["missing-the", "case-punctuation", "extra-also", "email", "fix-builder-detail",
        "earlier-adopted", "task-builder-detail", "task-of-to", "task-cpp", "task-prefix"])
def test_1_fixes_block_every_not_done_and_tasks_keep_matching(env, adopted, kind, owner, wording, blocks):
    setup_client(env, adopted)
    if kind == "fix":
        item, where = env.start_fix(done_when=owner)
    else:
        item, where = env.start_approved_task(NEW.replace("A shopper can save a basket.", owner))
    detail = "The worker brief uses a separate formatter"
    env.commit(where, "docs/implementation.md", f"# Builder details\n\n{detail}.\n")
    note = finding("P2", f"Not done: {wording}")
    note["body"] = "Gain 2, Work 4, Harm 1\nThe promised outcome is absent."
    env.reviews(blocked(note))

    closed = env.close(item)

    published = body(env.gh_calls("pr", "edit")[-1])
    if not blocks:
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


def test_2_upgrade_reclassifies_a_saved_fix_not_done_without_another_review(env):
    setup_client(env, True)
    command = earlier_close_command(env)
    item, _ = env.start_fix()
    note = finding("P2", "Not done: The worker brief uses a separate formatter")
    env.reviews(blocked(note))
    earlier = subprocess.run([sys.executable, str(command), "close", item], cwd=env.repo.path,
                             capture_output=True, text=True, timeout=60)
    assert earlier.returncode == 0, earlier.stdout + earlier.stderr
    env.open_pr(body((env.gh_calls("pr", "edit") or env.gh_calls("pr", "create"))[-1]))

    closed = env.close(item)

    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Review: blocked." in closed.stdout
    assert f"{note['title']} (app.py:1): blocks the merge" in body(env.gh_calls("pr", "edit")[-1])
    assert len(env.review_calls()) == 1, "The upgrade must reclassify the saved review"
