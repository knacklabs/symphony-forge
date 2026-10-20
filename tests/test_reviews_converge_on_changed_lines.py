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
    # A fix's first review keeps even owner-item P1s as follow-ups. Story
    # parts still block on a missed owner item in their first round.
    if owner_item and kind == "task":
        assert closed.returncode == 1 and note["title"].rstrip(".") in closed.stderr, closed.stdout + closed.stderr
    else:
        assert closed.returncode == 0, closed.stdout + closed.stderr
        shown = body(env.gh_calls("pr", "edit")[-1])
        assert "Follow-ups:" in shown and note["title"] in shown
        assert "blocks the merge" not in shown


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_3_review_convergence_owner_rule_answers_the_second_round_question(env, adopted):
    client(env, adopted)
    # Fixes now stop for the owner at their first P0; story parts own the
    # separate second-round advice and later hard-stop contract.
    item, where = env.start_approved_task(NEW)
    synced(env, where)
    # Round-two P1s now follow up; this retained owner-choice test needs genuine P0s.
    for number, title in enumerate(("Saving drops quantities", "Saving drops discounts"), 1):
        env.commit(where, "app.py", f"print('saving repair {number}')\n")
        env.reviews(blocked(finding("P0", title)))
        closed = env.close(item)
        assert closed.returncode == 1 and title in closed.stderr, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 2

    question = "Stop sending rounds and ask the owner to settle the missing rule."
    asked = env.repo.forge("next")
    assert asked.returncode == 0, asked.stdout + asked.stderr
    assert question in asked.stdout
    assert "Saving drops quantities" in asked.stdout and "Saving drops discounts" in asked.stdout

    # A code edit alone does not answer the owner's question.
    env.commit(where, "app.py", "print('another saving repair')\n")
    unanswered = env.repo.forge("next")
    assert unanswered.returncode == 0, unanswered.stdout + unanswered.stderr
    assert question in unanswered.stdout

    rule = "Owner rule: Saving keeps every basket line and its quantity."
    plan = "plans/SHOP.md"
    text = (where / plan).read_text("utf-8")
    anchor = "Tests save a two-line basket through the app."
    assert anchor in text
    env.commit(where, plan, text.replace(anchor, anchor + " " + rule), "Record the owner's saving rule")
    answered = env.repo.forge("next")
    assert answered.returncode == 0, answered.stdout + answered.stderr
    assert question not in answered.stdout, answered.stdout
    assert f"Next: forge work {item}" in answered.stdout, answered.stdout
    assert len(env.review_calls()) == 2
    for host in (".codex", ".claude"):
        guide = " ".join((where / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "`forge next` then shows the work step again." in guide
        assert "A hard stop still needs its resolve choice." in guide

    # The focused review may reach the genuine same-file stop. A later guidance
    # edit cannot substitute for the owner's explicit hard-stop resolution.
    env.reviews(blocked(finding("P0", "Saving drops names")))
    stopped = env.close(item)
    resolve = f"forge close {item} --resolve <narrow|split|accept>"
    assert stopped.returncode == 1 and resolve in stopped.stderr, stopped.stdout + stopped.stderr
    path = "plans/SHOP.md"
    env.commit(where, path, (where / path).read_text("utf-8") + "\nKeep the owner's rule.\n")
    held = env.repo.forge("next")
    assert held.returncode == 0 and resolve in held.stdout, held.stdout + held.stderr
    assert len(env.review_calls()) == 3
