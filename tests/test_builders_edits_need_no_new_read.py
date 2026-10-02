"""After a plan's latest round of cold read passed, an edit only below `## For the builders` needs
no new round, as it needs no new approval; an edit above it still does, and that round asks the
reader to check only the diff and the sections it touches. Everything runs the real forge command;
the reader is the stub `claude` from test_story.
"""

import json

from test_readloop_gates import pr_check
from test_story import DOC, claude_plan, hook, new_story, setup, worktree

STORY = "FIX-AFTER-A-PLAN-READ-PASSES-ANY-LATER-EDIT"

BUILT = DOC.replace("## Tasks", "## For the builders\n\n### Done-when details\n\n"
                                "1. Baskets are kept in the database.\n\n## Tasks")
TOP = BUILT.split("## For the builders")[0]


def _passed(repo):
    setup(repo)
    shop = new_story(repo, "SHOP")
    doc = shop / "plans" / "SHOP.md"
    doc.write_text(BUILT, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0 and "found nothing" in read.stdout, read.stdout + read.stderr
    return shop, doc


def test_1_a_builders_only_edit_after_a_pass_needs_no_round(repo, claude_payload):
    shop, doc = _passed(repo)
    doc.write_text(BUILT.replace("kept in the database.", "kept in the database, one per shopper."),
                   encoding="utf-8")
    shown = repo.forge("next").stdout
    assert "Shoppers can save a basket is waiting for approval." in shown, shown
    assert "forge read SHOP" not in shown, shown
    approved = hook(repo, claude_plan(claude_payload, TOP))
    assert approved.returncode == 0, approved.stderr
    # Another builders-only edit, committed this time, after approval: the task still starts.
    doc.write_text(doc.read_text("utf-8").replace("Save baskets |", "Store baskets |"), encoding="utf-8")
    repo.git("commit", "-q", "-am", "Tighten the details", cwd=shop)
    assert "forge read SHOP" not in repo.forge("next").stdout
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stderr


def test_2_a_top_part_edit_after_a_pass_needs_a_round_on_the_diff(repo, claude_payload):
    shop, doc = _passed(repo)
    doc.write_text(BUILT.replace("come back to it later.", "come back to it within a week."),
                   encoding="utf-8")
    edited = TOP.replace("come back to it later.", "come back to it within a week.")
    assert repo.forge("next").stdout.splitlines()[-2:] == [
        "Planning Shoppers can save a basket: plans/SHOP.md changed after round 1 of its cold read, "
        "so round 2 is next.",
        "Next: forge read SHOP"]
    refused = hook(repo, claude_plan(claude_payload, edited))
    assert (refused.returncode, refused.stderr) == (1, (
        "plans/SHOP.md changed after its last round of cold read.\nNext: forge read SHOP\n"))
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    prompt = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]
    for part in ("Round 2 of your cold read of `plans/SHOP.md`",
                 "Your last round found nothing, and the doc changed since.",
                 "-Shoppers can save a basket and come back to it later.",
                 "+Shoppers can save a basket and come back to it within a week.",
                 "It touches these sections: `## What changes for you`.",
                 "Check only this diff and the sections it touches"):
        assert part in prompt, part
    assert "read the whole doc again" not in prompt


def test_3_the_pull_request_check_accepts_only_a_builders_only_edit_after_a_pass(repo, claude_payload):
    _passed(repo)
    assert hook(repo, claude_plan(claude_payload, TOP)).returncode == 0
    assert repo.forge("task", "start", "SHOP/SAVE").returncode == 0
    task = worktree(repo, "task/SHOP-SAVE")
    doc = task / "plans" / "SHOP.md"
    # A committed edit only below For the builders: the doc check passes and the review is next.
    doc.write_text(BUILT.replace("kept in the database.", "kept in the database, one per shopper."),
                   encoding="utf-8")
    repo.git("commit", "-q", "-am", "Tighten the details", cwd=task)
    done = pr_check(repo, "task/SHOP-SAVE")
    assert done.stderr.splitlines()[-2] == "The committed review at the head of task/SHOP-SAVE is missing."
    # The same kind of edit above it is refused until a round reads it.
    doc.write_text(doc.read_text("utf-8").replace("People lose", "Shoppers lose"), encoding="utf-8")
    repo.git("commit", "-q", "-am", "Reword the why", cwd=task)
    done = pr_check(repo, "task/SHOP-SAVE")
    assert done.returncode == 1
    assert done.stderr.splitlines()[-2] == "plans/SHOP.md changed after its last round of cold read."
