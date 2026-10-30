"""Close keeps later reviews on repairs and owner-approved acceptance criteria.

Autoreview is the external service stub; Forge decides which findings hold close
and keeps advice visible in the pull request.
"""
import pytest

from test_close import GREEN, blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client as setup_client
from test_shortplan_briefs import NEW, SAVE_DETAILS

STORY = "reviews-converge"
CONVERGENCE = ("From the second review round, close checks the previous round's findings "
               "and new P0s that happen in normal use.")
OWNER_ACCEPTANCE = ("`Not done` blocks only against a numbered owner-approved Done-when item "
                    "(a fix uses its Done-when line). Builder details, Notes and implementation "
                    "guidance never block as `Not done`.")


def guides(where):
    for host in (".codex", ".claude"):
        text = (where / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert CONVERGENCE in " ".join(text.split()), host
        assert OWNER_ACCEPTANCE in " ".join(text.split()), host


def client(env, adopted):
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    # The shared fixture initializes or upgrades, then clones a separate main writer.
    setup_client(env, adopted)
    guides(env.repo.path)
    env.commit(env.repo.path, "forge.toml", config, "Use the test reader and checks")
    env.repo.git("push", "-q", "origin", "main")
    env.checks(GREEN)


def synced(env, where):
    result = env.repo.forge("sync", cwd=where)
    assert result.returncode == 0, result.stdout + result.stderr
    guides(where)
    env.repo.git("add", "-A", cwd=where)
    if env.repo.git("diff", "--cached", "--name-only", cwd=where).strip():
        env.repo.git("commit", "-q", "-m", "Sync client guidance", cwd=where)


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
@pytest.mark.parametrize("kind", ["fix", "task"])
@pytest.mark.parametrize("owner_item", [False, True], ids=["builder-detail", "owner-done-when"])
def test_2_review_convergence_not_done_blocks_only_an_owner_approved_item(env, adopted, kind, owner_item):
    client(env, adopted)
    if kind == "fix":
        owner = "The readme opens with a greeting"
        detail = "The greeting uses a separate formatter"
        item, where = env.start_fix()
        env.commit(where, "docs/implementation.md", f"# Builder guidance\n\n{detail}.\n")
    else:
        owner = "A shopper can save a basket."
        detail = SAVE_DETAILS
        item, where = env.start_approved_task(NEW)
    synced(env, where)
    note = finding("P1", "Not done: " + (owner if owner_item else detail))
    env.reviews(blocked(note))
    closed = env.close(item)
    assert len(env.review_calls()) == 1, closed.stdout + closed.stderr
    # A missed owner item blocks both kinds; a fix also reaches its review limit.
    if owner_item:
        assert closed.returncode == 1 and note["title"].rstrip(".") in closed.stderr, closed.stdout + closed.stderr
        if kind == "fix":
            assert "reached the round limit with open findings" in closed.stderr
    else:
        assert closed.returncode == 0, closed.stdout + closed.stderr
        shown = body(env.gh_calls("pr", "edit")[-1])
        assert "Follow-ups:" in shown and note["title"] in shown
        assert "blocks the merge" not in shown
