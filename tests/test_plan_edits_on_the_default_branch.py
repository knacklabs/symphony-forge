STORY = "FIX-FORGE-NEXT-AND-FORGE-TASK-START-READ-A-S"
"""A plan edit that reaches the default branch another way (a fix) after a task merged: forge next
says the story branch lacks it, and forge task start merges the default branch into the story
branch before it reads the task rows, refusing and changing nothing when that merge conflicts.
Everything runs the real forge command. Each test is named test_<n>_<rule> after the Done-when item
of STORY it proves.
"""

from test_readloop_gates import approve, read
from test_story import DOC, setup, new_story

# The fix's plan edit: a new task FIX that SHOW now waits for.
FIXED = DOC.replace("| `tests/test_page.py` | SAVE | yes |",
                    "| `tests/test_page.py` | SAVE, FIX | yes |\n"
                    "| FIX | Fix the clock | The time is right | 2 | `src/clock.py` | "
                    "`tests/test_clock.py` | SAVE | no |")
LACKS = "The default branch has changes to plans/SHOP.md that story/SHOP lacks."
CHANGED = "plans/SHOP.md changed after its last round of cold read.\nNext: forge read SHOP\n"


def _saved_then_fixed(repo, claude_payload):
    """SHOP approved, SAVE squash-merged, then a fix edits the plan on the default branch."""
    setup(repo)
    shop = new_story(repo, "SHOP")
    (shop / "plans" / "SHOP.md").write_text(DOC, encoding="utf-8")
    read(repo)
    approve(repo, claude_payload, DOC)
    assert repo.forge("task", "start", "SHOP/SAVE").returncode == 0
    repo.git("merge", "-q", "--squash", "task/SHOP-SAVE")
    repo.git("commit", "-q", "-m", "Save baskets (#1)")
    repo.write("plans/SHOP.md", FIXED)
    repo.git("commit", "-q", "-am", "Fix: SHOW waits for a clock fix (#2)")
    repo.git("push", "-q", "origin", "main")
    repo.git("fetch", "-q", "origin")
    return shop


def _said(repo, line):
    """The line forge next prints right after this one."""
    lines = repo.forge("next").stdout.splitlines()
    assert line in lines, lines
    return lines[lines.index(line) + 1]


def test_1_next_says_the_story_branch_lacks_plan_edits(repo, claude_payload):
    shop = _saved_then_fixed(repo, claude_payload)
    # Before: SHOW was listed as startable from the story branch's old rows.
    assert _said(repo, LACKS) == f"Next: git -C {shop} merge origin/main"
    assert "Next: forge task start SHOP/SHOW" not in repo.forge("next").stdout
    # With no story folder, the command makes it first.
    repo.git("worktree", "remove", str(shop))
    assert _said(repo, LACKS) == f"Next: git worktree add {shop} story/SHOP, then git -C {shop} merge origin/main"


def test_2_task_start_merges_the_default_branch_first(repo, claude_payload):
    shop = _saved_then_fixed(repo, claude_payload)
    started = repo.forge("task", "start", "SHOP/SHOW")
    assert started.stdout == "Merged origin/main into story/SHOP.\n", started.stderr
    assert (started.returncode, started.stderr) == (1, CHANGED)
    assert (shop / "plans" / "SHOP.md").read_text("utf-8") == FIXED
    assert repo.git("merge-base", "--is-ancestor", "origin/main", "story/SHOP") == ""
    assert LACKS not in repo.forge("next").stdout

    # Read again on the merged plan: SHOW now waits for FIX, as the merged plan says.
    read(repo)
    refused = repo.forge("task", "start", "SHOP/SHOW")
    assert (refused.returncode, refused.stderr) == (
        1, "SHOP/SHOW waits for SHOP/FIX to merge first.\nNext: forge next\n")
    assert repo.forge("task", "start", "SHOP/FIX").returncode == 0


def test_3_a_merge_that_fails_refuses_and_changes_nothing(repo, claude_payload):
    shop = _saved_then_fixed(repo, claude_payload)
    doc = shop / "plans" / "SHOP.md"
    before = repo.git("rev-parse", "story/SHOP")

    # Uncommitted edits the merge would overwrite.
    edited = DOC.replace("come back to it later", "come back to it any day")
    doc.write_text(edited, encoding="utf-8")
    refused = repo.forge("task", "start", "SHOP/SHOW")
    assert (refused.returncode, refused.stdout, refused.stderr) == (1, "", (
        "Merging origin/main into story/SHOP conflicts in its uncommitted edits, so Forge changed "
        "nothing.\nNext: merge origin/main into story/SHOP by hand, then forge task start SHOP/SHOW\n"))
    assert repo.git("rev-parse", "story/SHOP") == before
    assert doc.read_text("utf-8") == edited

    # A committed edit to the same row conflicts.
    doc.write_text(DOC.replace("| SAVE | yes |", "| none | yes |"), encoding="utf-8")
    repo.git("commit", "-q", "-am", "SHOW no longer waits", cwd=shop)
    before = repo.git("rev-parse", "story/SHOP")
    refused = repo.forge("task", "start", "SHOP/SHOW")
    assert (refused.returncode, refused.stdout, refused.stderr) == (1, "", (
        "Merging origin/main into story/SHOP conflicts in plans/SHOP.md, so Forge changed nothing.\n"
        "Next: merge origin/main into story/SHOP by hand, then forge task start SHOP/SHOW\n"))
    assert repo.git("rev-parse", "story/SHOP") == before
    assert repo.git("status", "--porcelain", cwd=shop) == ""
    assert "task/SHOP-SHOW" not in repo.git("branch", "--list", "task/*")
