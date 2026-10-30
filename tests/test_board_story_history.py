"""A story's history in the board's facts lists each cold-read round of its plan, its findings and
how each was answered, its approver and its merged part. Only the reader is a stub; board output is
all the test reads."""
import json
import re

from test_board import DOC
from test_board_dependency_timelines import _configured, _land_fixture
from test_story import claude_plan, hook, new_story, worktree

STORY = "FORGE-BOARD-2"


def _answer(notes, number, disposition):
    """Write a disposition under finding `number`, as a person answering the read does."""
    text = notes.read_text("utf-8")
    text = re.sub(rf"^({number}\. .*)$", rf"\1\n   Disposition: {disposition}", text, count=1, flags=re.M)
    notes.write_text(text, encoding="utf-8")


def story_history_lists_read_rounds(repo, gh, tmp_path, claude_payload, history):
    """Run from criterion 12's one test in tests/test_board_how_it_went.py."""
    _configured(repo, gh, tmp_path, history, ("SHOP",))
    says = repo.bin / "claude-says.md"
    shop = new_story(repo, "SHOP")
    doc, notes = shop / "plans/SHOP.md", shop / "plans/SHOP.read.md"
    doc.write_text(DOC, encoding="utf-8")

    # Round one retains each human answer: cut, keep and defer.
    says.write_text("1. Saving needs sign-in first.\n2. The basket limit is unclear.\n"
                   "3. Saved baskets have no expiry rule.\n", encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    _answer(notes, 1, "cut")
    _answer(notes, 2, "keep because shoppers asked for no limit")
    _answer(notes, 3, "defer")
    amended = DOC.replace("come back to it later", "come back to it on another day")
    doc.write_text(amended, encoding="utf-8")
    # Round two stops for an owner choice; the board keeps the owner's answer.
    says.write_text("4. The empty basket message is missing.\n", encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 1 and "asks the owner" in read.stderr, read.stdout + read.stderr
    accepted = repo.forge("read", "SHOP", "--resolve", "accept", "--reason",
                          "the owner accepts the missing message note")
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    approved = hook(repo, claude_plan(claude_payload, amended, cwd=shop))
    assert approved.returncode == 0, approved.stderr
    # One part built and merged after the approval.
    repo.git("merge", "-q", "--no-edit", "story/SHOP")
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stdout + started.stderr
    part = worktree(repo, "task/SHOP-SAVE")
    (part / "basket.txt").write_text("saved\n", encoding="utf-8")
    repo.git("add", "-A", cwd=part)
    repo.git("commit", "-qm", "Save a basket", cwd=part)
    repo.git("merge", "-q", "--no-edit", "task/SHOP-SAVE")
    _land_fixture(repo)

    data = json.loads(repo.forge("board", "--json").stdout)
    row = next(item for item in data["items"] if item["id"] == "SHOP")
    rounds = row["read_rounds"]
    assert [r["round"] for r in rounds] == [1, 2]
    assert rounds[0]["findings"] == [
        {"title": "Saving needs sign-in first.", "disposition": "cut", "reason": None},
        {"title": "The basket limit is unclear.", "disposition": "keep", "reason": "shoppers asked for no limit"},
        {"title": "Saved baskets have no expiry rule.", "disposition": "defer", "reason": None}]
    assert rounds[1]["findings"] == [
        {"title": "The empty basket message is missing.", "disposition": "keep",
         "reason": "the owner accepts the missing message note"}]
    # Only the latest round is dated.
    assert rounds[0]["read_at"] is None and rounds[1]["read_at"]

    assert row["approved_by"]
    merged = next(part for part in row["children"] if part["id"] == "SHOP/SAVE")
    assert merged["state"] == "done", merged["state"]
