"""Approved plans remain droppable before any part starts."""
import json

from test_start_sorts_ideas import (intake, _signed_off, _started, _plan,
                                    _checkout, _land_setup)  # noqa: F401
from test_close import env  # noqa: F401
from test_land import land  # noqa: F401
from test_story import DOC, approved_constitution, claude_plan

STORY = "FIX-DROP-APPROVED-UNSTARTED-STORY"


def test_1_approved_unstarted_story_can_drop(intake, claude_payload):
    repo, top, owner, *_ = intake
    _signed_off(intake)
    approved_constitution(repo, where=top)
    roadmap = top / "plans/roadmap.json"
    data = json.loads(roadmap.read_text("utf-8")) if roadmap.exists() else {"items": []}
    data["items"].append({"key": "APPROVED", "title": "Keep baskets for later"})
    roadmap.write_text(json.dumps(data), "utf-8")
    _land_setup(repo, top, "record-roadmap")
    _started(intake, "Another saved basket", _plan("APPROVED"))
    where = _checkout(repo, top, "story/APPROVED")
    approved_doc = DOC.replace("| yes |", "| no |")
    (where / "plans/APPROVED.md").write_text(approved_doc, "utf-8")
    read = owner.forge("read", "APPROVED", cwd=where)
    assert read.returncode == 0, read.stdout + read.stderr
    if read.stdout.lstrip().startswith("{"):
        handout = json.loads(read.stdout)
        read = owner.forge("handback", "APPROVED", "--round", str(handout["round"]),
                           "--subagent", "plan-reader", "--text", "No findings.", cwd=where)
        assert read.returncode == 0, read.stdout + read.stderr
    approval = repo.forge("hook", "approval", input=json.dumps(claude_plan(
        claude_payload, approved_doc, cwd=where)), cwd=where)
    assert approval.returncode == 0, approval.stdout + approval.stderr
    dropped = repo.forge("story", "drop", "APPROVED", "--because", "Keep it for later", cwd=top)
    assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    assert "Its remote branch keeps the work." in dropped.stdout
    assert repo.git("ls-remote", "origin", "refs/heads/story/APPROVED", cwd=top)
    assert repo.git("show", "origin/story/APPROVED:plans/APPROVED.md", cwd=top) == approved_doc.rstrip()
    assert "APPROVED" not in repo.forge("next", cwd=top).stdout
    board = repo.forge("board", "--json", cwd=top)
    assert board.returncode == 0, board.stdout + board.stderr
    assert "APPROVED" not in {row["id"] for row in json.loads(board.stdout)["items"]}
    assert json.loads(roadmap.read_text("utf-8")) == data
    # Revert the drop on its retained branch, as for an unapproved plan.
    repo.git("worktree", "add", "-q", "-b", "story/APPROVED", str(where),
             "origin/story/APPROVED", cwd=top)
    repo.git("revert", "--no-edit", "HEAD", cwd=where)
    repo.git("push", "-q", "origin", "story/APPROVED", cwd=where)
    assert "APPROVED" in repo.forge("next", cwd=top).stdout
    started = repo.forge("task", "start", "APPROVED/SAVE", cwd=top)
    assert started.returncode == 0, started.stdout + started.stderr
    refused = repo.forge("story", "drop", "APPROVED", "--because", "Keep it for later", cwd=top)
    assert refused.returncode == 1
    assert refused.stderr == ("APPROVED has started parts, so it cannot be dropped.\n"
                              "Next: forge close APPROVED/SAVE\n")
