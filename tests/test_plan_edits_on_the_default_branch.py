STORY = "FIX-FORGE-NEXT-AND-FORGE-TASK-START-READ-A-S"
"""A plan edit that reaches the default branch another way (a fix) after a task merged: forge next
says the story branch lacks it, with the command that merges it in, and forge task start refuses
with the same line, changing nothing. Neither merges anything. Everything runs the real forge
command. Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""

from shlex import quote

from test_readloop_gates import approve, read
from test_story import DOC, setup, new_story

# The fix's plan edit: a new task FIX that SHOW now waits for.
FIXED = DOC.replace("| `tests/test_page.py` | SAVE | yes |",
                    "| `tests/test_page.py` | SAVE, FIX | yes |\n"
                    "| FIX | Fix the clock | The time is right | 2 | `src/clock.py` | "
                    "`tests/test_clock.py` | SAVE | no |")
LACKS = "The default branch has changes to plans/SHOP.md that story/SHOP lacks; merge them in with "


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
    notice = f"{LACKS}git -C {quote(str(shop))} merge origin/main"

    # forge next no longer lists SHOW from the story branch's old rows; it prints one line naming the merge.
    lines = repo.forge("next").stdout.splitlines()
    assert notice in lines
    assert not any(line.startswith("Next: forge task start SHOP/SHOW") for line in lines)

    refused = repo.forge("task", "start", "SHOP/SHOW")
    assert (refused.returncode, refused.stdout, refused.stderr) == (1, "", f"{notice}\n")
    assert repo.git("rev-parse", "story/SHOP") == before
    assert repo.git("status", "--porcelain", cwd=shop) == ""
    assert "task/SHOP-SHOW" not in repo.git("branch", "--list", "task/*")

    # With no story folder, the command makes it first; a folder with a space is quoted.
    repo.git("worktree", "remove", str(shop))
    assert f"{LACKS}git worktree add {quote(str(shop))} story/SHOP && git -C {quote(str(shop))} merge origin/main" in (
        repo.forge("next").stdout.splitlines())
    spaced = shop.with_name("story folder")
    repo.git("worktree", "add", "-q", str(spaced), "story/SHOP")
    assert f"{LACKS}git -C {quote(str(spaced))} merge origin/main" in repo.forge("next").stdout.splitlines()


def test_2_identical_copies_are_not_flagged(repo, claude_payload):
    _saved(repo, claude_payload)
    repo.git("fetch", "-q", "origin")

    lines = repo.forge("next").stdout.splitlines()
    assert not any(line.startswith(LACKS) for line in lines)
    assert "Next: forge task start SHOP/SHOW  # Codex builds it" in lines
    started = repo.forge("task", "start", "SHOP/SHOW")
    assert started.returncode == 0, started.stderr


def test_3_a_later_dated_story_edit_still_lacks_independent_main_changes(repo, claude_payload, monkeypatch):
    shop = _saved(repo, claude_payload)
    _fixed(repo, monkeypatch)
    # Commit dates used to hide independent main changes. Content history now keeps them blocked,
    # even after a later story edit outside what the approval binds.
    (shop / "plans" / "SHOP.md").write_text(DOC.replace("People lose their basket when they leave.",
                                                        "People lose their basket when they close the tab."),
                                            encoding="utf-8")
    _commit_later(repo, monkeypatch, "2031-01-01T00:00:00", "-am", "Reword the plan", cwd=shop)
    read(repo)

    lines = repo.forge("next").stdout.splitlines()
    notice = f"{LACKS}git -C {quote(str(shop))} merge origin/main"
    assert notice in lines
    assert "Next: forge task start SHOP/SHOW  # Codex builds it" not in lines
    started = repo.forge("task", "start", "SHOP/SHOW")
    assert (started.returncode, started.stdout, started.stderr) == (1, "", f"{notice}\n")
