"""Boards keep completed assignments and accept Markdown-formatted task IDs."""
import json

import pytest

from test_board import DOC, seen
from test_machine_views_recent_finished_items import client, landed, NOW, OLD

STORY = "FIX-SKIPPED-SYNC-BOARD"


def assigned_doc():
    return DOC.replace("| User-facing |", "| User-facing | Developer |").replace(
        "| no |", "| no | Ada |").replace("| yes |", "| yes | Ada |")


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_merged_assignment_older_than_seven_days_is_never_unstarted(
        repo, gh, monkeypatch, tmp_path, history):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    landed(repo, monkeypatch, OLD, {
        "plans/SHOP.md": assigned_doc(),
        ".factory/stories/SHOP/story.json": {"status": "approved", "title": "Save a basket",
                                               "approval": {"at": OLD}},
        ".factory/stories/SHOP/tasks/SAVE.json": {"status": "waiting for checks"},
    })
    result = repo.forge("board", "--json")
    assert result.returncode == 0, result.stderr
    story = next(r for r in json.loads(result.stdout)["items"] if r["id"] == "SHOP")
    assert "SHOP/SAVE" not in {r["id"] for r in story["children"]}, "Old merged work stays outside active rows"
    out = tmp_path / "board.html"
    result = repo.forge("board", "--out", out.as_posix())
    assert result.returncode == 0, result.stderr
    assert "In progress: 1 of 3 parts finished." in seen(out)


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_backticked_task_ids_render_on_both_boards(repo, gh, monkeypatch, tmp_path, history):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    doc = assigned_doc()
    for tid in ("SAVE", "SHOW", "SHARE"):
        doc = doc.replace(f"| {tid} |", f"| `{tid}` |")
    landed(repo, monkeypatch, NOW, {
        "plans/SHOP.md": doc,
        ".factory/stories/SHOP/story.json": {"status": "approved", "title": "Save a basket"},
    })
    result = repo.forge("board", "--json")
    assert result.returncode == 0, result.stderr
    story = next(r for r in json.loads(result.stdout)["items"] if r["id"] == "SHOP")
    assert {r["id"] for r in story["children"]} == {"SHOP/SAVE", "SHOP/SHOW", "SHOP/SHARE"}
    out = tmp_path / "board.html"
    result = repo.forge("board", "--out", out.as_posix())
    assert result.returncode == 0, result.stderr
    assert all(name in seen(out) for name in ("Save a basket", "Show when it was saved", "Share a basket"))
