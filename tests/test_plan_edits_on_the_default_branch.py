STORY = "FIX-FORGE-NEXT-AND-FORGE-TASK-START-READ-A-S"
"""A plan edit that reaches the default branch another way (a fix) after a task merged: forge next
says the story branch lacks it, with the command that merges it in, and forge task start refuses
with the same line, changing nothing. Neither merges anything. Everything runs the real forge
command. Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""

from test_readloop_gates import approve, read
from test_story import DOC, setup, new_story

# The fix's plan edit: a new task FIX that SHOW now waits for.
FIXED = DOC.replace("| `tests/test_page.py` | SAVE | yes |",
                    "| `tests/test_page.py` | SAVE, FIX | yes |\n"
                    "| FIX | Fix the clock | The time is right | 2 | `src/clock.py` | "
                    "`tests/test_clock.py` | SAVE | no |")
LACKS = "The default branch has changes to plans/SHOP.md that story/SHOP lacks."


def _saved(repo, claude_payload):
    """SHOP approved and SAVE squash-merged: the default branch holds the story branch's plan."""
    setup(repo)
    shop = new_story(repo, "SHOP")
    (shop / "plans" / "SHOP.md").write_text(DOC, encoding="utf-8")
    read(repo)
    approve(repo, claude_payload, DOC)
    assert repo.forge("task", "start", "SHOP/SAVE").returncode == 0
    repo.git("merge", "-q", "--squash", "task/SHOP-SAVE")
    repo.git("commit", "-q", "-m", "Save baskets (#1)")
    repo.git("push", "-q", "origin", "main")
    return shop


def _commit_later(repo, monkeypatch, when, *args, cwd=None):
    """A commit dated after everything else, so "newer" never hangs on the same second."""
    monkeypatch.setenv("GIT_COMMITTER_DATE", when)
    repo.git("commit", "-q", *args, cwd=cwd)
    monkeypatch.delenv("GIT_COMMITTER_DATE")


def _fixed(repo, monkeypatch):
    """A fix edits the plan on the default branch after the approval."""
    repo.write("plans/SHOP.md", FIXED)
    _commit_later(repo, monkeypatch, "2030-01-01T00:00:00", "-am", "Fix: SHOW waits for a clock fix (#2)")
    repo.git("push", "-q", "origin", "main")
    repo.git("fetch", "-q", "origin")


def test_1_a_plan_edited_on_the_default_branch_is_flagged_and_refused(repo, claude_payload, monkeypatch):
    shop = _saved(repo, claude_payload)
    _fixed(repo, monkeypatch)
    before = repo.git("rev-parse", "story/SHOP")
    command = f"git -C {shop} merge origin/main"

    # forge next no longer lists SHOW from the story branch's old rows; it names the merge.
    lines = repo.forge("next").stdout.splitlines()
    assert lines[lines.index(LACKS) + 1] == f"Next: {command}"
    assert "Next: forge task start SHOP/SHOW" not in lines

    refused = repo.forge("task", "start", "SHOP/SHOW")
    assert (refused.returncode, refused.stdout, refused.stderr) == (1, "", f"{LACKS}\nNext: {command}\n")
    assert repo.git("rev-parse", "story/SHOP") == before
    assert repo.git("status", "--porcelain", cwd=shop) == ""
    assert "task/SHOP-SHOW" not in repo.git("branch", "--list", "task/*")

    # With no story folder, the command makes it first.
    repo.git("worktree", "remove", str(shop))
    lines = repo.forge("next").stdout.splitlines()
    assert lines[lines.index(LACKS) + 1] == (
        f"Next: git worktree add {shop} story/SHOP, then git -C {shop} merge origin/main")


def test_2_identical_copies_are_not_flagged(repo, claude_payload):
    _saved(repo, claude_payload)
    repo.git("fetch", "-q", "origin")

    lines = repo.forge("next").stdout.splitlines()
    assert LACKS not in lines
    assert "Next: forge task start SHOP/SHOW" in lines
    started = repo.forge("task", "start", "SHOP/SHOW")
    assert started.returncode == 0, started.stderr


def test_3_a_newer_story_branch_edit_is_not_flagged(repo, claude_payload, monkeypatch):
    shop = _saved(repo, claude_payload)
    _fixed(repo, monkeypatch)
    # The story branch edits its plan after the default branch did.
    (shop / "plans" / "SHOP.md").write_text(DOC.replace("come back to it later", "come back to it any day"),
                                            encoding="utf-8")
    _commit_later(repo, monkeypatch, "2031-01-01T00:00:00", "-am", "Reword the plan", cwd=shop)

    assert LACKS not in repo.forge("next").stdout
    refused = repo.forge("task", "start", "SHOP/SHOW")
    assert LACKS not in refused.stderr
