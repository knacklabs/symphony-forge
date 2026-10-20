"""Release facts through the real board command, with real Git ancestry.

Exercises src/forge/releases.py and src/forge/board.py.

Audit: filtering tags, inventing lightweight dates or releasing a story early
changes the public result. No existing test owns these facts. Only GitHub and
the upgrade installer are faked; no production test seam supplies the result.
"""
import json
import shutil
from datetime import datetime

import pytest

from conftest import ROOT
from test_board_counts import board, rows
from test_close import STORY_DOC, env  # noqa: F401
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FORGE-BOARD-3"


@pytest.mark.parametrize("history", ["new-annotated", "new-lightweight", "earlier-adoption"])
def test_5_board_lists_tagged_releases_and_each_items_first_release(unsynced_up, monkeypatch, history):
    up, env = unsynced_up, unsynced_up.env
    repo = env.repo
    repo.git("config", "core.hooksPath", (up.tmp / "no-hooks").as_posix())
    if history == "earlier-adoption":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        env.commit(repo.path, "forge.toml", (repo.path / "forge.toml").read_text("utf-8"), "Adopt Forge")
    at = "2026-10-19T12:00:00+00:00"
    for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.setenv(name, at)

    def land(item, kind="task", finished=False):
        branch = f"task/{item.replace('/', '-')}" if kind == "task" else f"fix/{item}"
        path = (f".factory/stories/{item.split('/')[0]}/tasks/{item.split('/')[1]}.json"
                if kind == "task" else f".factory/fixes/{item}.json")
        repo.git("switch", "-q", "-c", branch)
        env.commit(repo.path, path, json.dumps({"kind": kind, "branch": branch, "status": "ready",
                   "why": "Clear help", "steps": [{"step": "start", "at": at}]}), "Write a part")
        if finished:
            env.commit(repo.path, f".factory/stories/{item.split('/')[0]}/story.json", json.dumps({
                "status": "done", "title": "Save a basket", "finished": at}), "Finish the story")
        repo.git("switch", "-q", "main")
        if kind == "fix":
            repo.git("merge", "-q", "--squash", branch)
            repo.git("commit", "-qm", "Clear help")
        else:
            repo.git("merge", "-q", "--no-ff", "-m", "Finish a part", branch)
        repo.git("branch", "-D", branch)

    env.commit(repo.path, "plans/SHIP.md", STORY_DOC, "Plan the basket")
    env.commit(repo.path, ".factory/stories/SHIP/story.json", json.dumps({
        "status": "approved", "title": "Save a basket", "approval": {"at": at}}), "Approve the basket")
    land("SHIP/T1")
    env.commit(repo.path, "plans/OLD.md", STORY_DOC.split("| T2 |")[0] + "\nNew moving parts: none\n",
               "Plan the first story")
    env.commit(repo.path, ".factory/stories/OLD/story.json", json.dumps({
        "status": "approved", "title": "An earlier basket"}), "Approve the first story")
    land("OLD/T1", finished=True)
    land("old-help", "fix")
    repo.git("push", "-q", "origin", "main")
    empty = board(repo)
    assert empty["releases"] == []
    assert empty["release_note"] == "no releases tagged"
    assert all(row["released_in"] is None for row in rows(empty).values())
    repo.git("switch", "-q", "-c", "unreleased-branch")
    env.commit(repo.path, "unreleased.txt", "not on main\n", "Unreleased work")
    repo.git("tag", "v0.1.0")
    repo.git("switch", "-q", "main")
    repo.git("tag", "v0.2.0", repo.git("rev-parse", "HEAD:README.md"))
    for tag in ("forge-start/example", "forge-plan/example", "demo"):
        repo.git("tag", tag)
    annotated = history != "new-lightweight"
    if annotated:
        monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-10-19T13:00:00+00:00")
        repo.git("tag", "-a", "v1.0.0", "-m", "First release")
    else:
        repo.git("tag", "v1.0.0")
    repo.git("push", "-q", "origin", "--tags")
    partial = board(repo)
    assert rows(partial)["SHIP"]["released_in"] is None
    assert rows(partial)["SHIP"]["plan_to_release_seconds"] is None
    assert rows(partial)["SHIP/T1"]["released_in"] == "v1.0.0"
    assert rows(partial)["OLD"]["released_in"] == "v1.0.0"
    assert rows(partial)["OLD"]["plan_to_release_seconds"] == (3600 if annotated else None)
    land("SHIP/T2", finished=True)
    repo.git("tag", "1.1.0-rc.1")
    land("next-help", "fix")
    repo.git("push", "-q", "origin", "main", "--tags")
    publication = [{"tag_name": "v1.0.0", "published_at": "2026-10-19T14:00:00Z"}]
    env.gh.respond("api", "repos/{owner}/{repo}/releases", stdout=json.dumps([
        publication if history == "earlier-adoption" else [], [{
        "tag_name": "1.1.0-rc.1", "published_at": "2026-10-20T10:00:00Z",
        "created_at": "2026-10-18T10:00:00Z"}]]))
    monkeypatch.setenv("FORGE_NOW", "2026-10-20T12:00:00+00:00")
    if history == "earlier-adoption":
        upgraded = up.run(RELEASE)
        assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    result = board(repo)
    normalized = [{**release, "date": datetime.fromisoformat(release["date"]).isoformat()
                   if release["date"] else None} for release in result["releases"]]
    first_date = ("2026-10-19T14:00:00+00:00" if history == "earlier-adoption" else
                  "2026-10-19T13:00:00+00:00" if annotated else None)
    assert normalized == [
        {"tag": "v1.0.0", "date": first_date,
         "items": ["OLD", "OLD/T1", "SHIP/T1", "old-help"]},
        {"tag": "1.1.0-rc.1", "date": "2026-10-20T10:00:00+00:00", "items": ["SHIP", "SHIP/T2"]}]
    assert not result.get("release_note")
    found = rows(result)
    assert found["SHIP"]["released_in"] == "1.1.0-rc.1"
    assert found["SHIP"]["plan_to_release_seconds"] == 79200
    assert found["OLD"]["plan_to_release_seconds"] == (7200 if history == "earlier-adoption" else
                                                        3600 if annotated else None)
    assert found["SHIP/T1"]["released_in"] == "v1.0.0"
    assert found["SHIP/T2"]["released_in"] == "1.1.0-rc.1"
    assert found["old-help"]["released_in"] == "v1.0.0"
    assert found["next-help"]["released_in"] is None
    monkeypatch.setenv("FORGE_NOW", "2027-01-20T12:00:00+00:00")
    assert board(repo)["releases"] == result["releases"]
