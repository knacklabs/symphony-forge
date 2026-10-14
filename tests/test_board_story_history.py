"""A story's history on the board lists each cold-read round of its plan, its findings and how
each was answered, before the approval. Only the reader is a stub; board output is all the test
reads."""
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

    # Round 1: two findings, one cut from the plan and one kept with a reason.
    says.write_text("1. Saving needs sign-in first.\n2. The basket limit is unclear.\n", encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    _answer(notes, 1, "cut")
    _answer(notes, 2, "keep because shoppers asked for no limit")
    amended = DOC.replace("come back to it later", "come back to it on another day")
    doc.write_text(amended, encoding="utf-8")
    # Round 2: one finding, deferred. Round 3: nothing found, so the plan passes.
    says.write_text("3. The empty basket message is missing.\n", encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    _answer(notes, 3, "defer")
    says.unlink()
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stderr
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
    assert [r["round"] for r in rounds] == [1, 2, 3]
    assert rounds[0]["findings"] == [
        {"title": "Saving needs sign-in first.", "disposition": "cut", "reason": None},
        {"title": "The basket limit is unclear.", "disposition": "keep", "reason": "shoppers asked for no limit"}]
    assert rounds[1]["findings"] == [
        {"title": "The empty basket message is missing.", "disposition": "defer", "reason": None}]
    assert rounds[2]["findings"] == []
    # Only the latest round is dated.
    assert rounds[0]["read_at"] is None and rounds[1]["read_at"] is None and rounds[2]["read_at"]

    out = tmp_path / "history.html"
    assert repo.forge("board", "--out", str(out)).returncode == 0
    page = out.read_text("utf-8")
    history = re.search(r'<ol class="history">(.*?)</ol>', page, re.S)
    assert history, "The story's history is on the page"
    lines = [" ".join(re.sub(r"<[^>]+>", " ", item).split())
             for item in re.findall(r'<li class="step">(.*?)</li>(?=<li class="step">|$)', history[1], re.S)]
    approval = next(n for n, line in enumerate(lines) if line.startswith("Plan approved"))
    expected = ["Cold read round 1: Saving needs sign-in first. Cut. "
                "The basket limit is unclear. Kept: shoppers asked for no limit.",
                "Cold read round 2: The empty basket message is missing. Deferred.",
                "Cold read round 3"]
    assert lines[:approval][:2] == expected[:2], lines
    assert lines[2].startswith(expected[2]) and lines[2].endswith("No findings."), lines
    assert approval == 3 and row["approved_by"] and row["approved_by"] in lines[approval]
    merged = next(part for part in row["children"] if part["id"] == "SHOP/SAVE")
    assert merged["state"] == "done", merged["state"]
    assert lines[approval + 1].startswith(f'{merged["title"]} merged'), lines
