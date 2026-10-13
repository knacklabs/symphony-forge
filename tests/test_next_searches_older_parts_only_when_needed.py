"""A cold next JSON refresh asks for older merges only for unfinished stories that need them."""
import json

import pytest

from test_machine_views_recent_finished_items import NOW, client, finished_story, landed
from test_machine_views_stay_fast import lists
from test_story import DOC

STORY = "next-no-extra-search"
OLD = "2026-09-01T12:00:00+00:00"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("parts,status,weekly,expected", [
    (False, "approved", False, 0),
    (True, "done", False, 0),
    (True, "approved", True, 0),
    (True, "approved", False, 1),
])
def test_1_next_json_searches_older_merges_only_for_unfinished_older_parts(
        repo, gh, monkeypatch, history, parts, status, weekly, expected):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    files = {
        ".factory/stories/LIVE/story.json": {**finished_story("LIVE", OLD), "status": status},
        "plans/LIVE.md": DOC,
    }
    if parts:
        files[".factory/stories/LIVE/tasks/SAVE.json"] = {
            "status": "waiting for checks", "branch": "task/LIVE-SAVE", "touches": 0}
    landed(repo, monkeypatch, OLD, files)
    if weekly:
        gh.respond("pr", "list", "--state", "merged", stdout=json.dumps([{
            "headRefName": "task/LIVE-SAVE", "mergedAt": "2026-11-01T12:00:00+00:00",
            "state": "MERGED", "body": "", "title": "Save baskets"}]))
    before = len(lists(gh))
    shown = repo.forge("next", "--json")
    assert shown.returncode == 0, shown.stderr
    assert "items" in json.loads(shown.stdout)
    calls = lists(gh)[before:]
    older = [call for call in calls if any(arg.startswith("merged:*..") for arg in call)]
    assert len(older) == expected, calls
    assert len(calls) == 8 + expected, "cold refresh needs only the open list, seven weeks and needed older parts"
