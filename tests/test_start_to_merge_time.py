"""Command proof for elapsed merge time and the daily board figure.

Audit: missing output and using ready time or other days are credible regressions
not covered by history retention tests. Only external services are fake.
No production seam is needed.
"""
import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from test_close import STORY_DOC, env  # noqa: F401
from test_last_task_records_story_outcome import github_merge
from test_board_how_it_went import published

STORY = "FIX-START-TO-MERGE-TIME"


def prepare(env, task=False):
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    start = (datetime.now(timezone.utc) - timedelta(hours=3, minutes=12)).replace(microsecond=0)
    if task:
        item, where = env.start_approved_task(STORY_DOC)
        path = f".factory/stories/SHOP/tasks/T1.json"
        state = json.loads((where / path).read_text("utf-8"))
        env.commit(where, path, json.dumps({**state, "steps": [{"step": "start", "at": start.isoformat()}]}))
    else:
        item, where = env.start_fix(round=1, steps=[{"step": "start", "at": start.isoformat()}])
    events = env.repo.path / ".git/forge/events.jsonl"
    events.parent.mkdir(exist_ok=True)
    events.write_text("".join(json.dumps(row) + "\n" for row in [
        {"item": item, "event": "work phase", "phase": "building", "round": 1, "at": start.isoformat()},
        {"item": item, "event": "owner wait start", "reason": "merge", "id": "owner", "round": 1,
         "at": (start + timedelta(minutes=1)).isoformat()},
    ]), "utf-8")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    return item, where, start


@pytest.mark.parametrize("command,task", [("merge", False), ("land", False), ("merge", True)])
def test_1_merge_and_land_print_start_to_merge_time(env, command, task):
    item, _, start = prepare(env, task)
    github_merge(env, "task/SHOP-T1" if task else f"fix/{item}")
    result = env.repo.forge(command, item)
    assert result.returncode == 0, result.stdout + result.stderr
    assert re.search(rf"Merged {item}: started {re.escape(start.isoformat())}, merged \S+, "
                     r"3h1[2-3]m start to merge; biggest wait: waiting for the owner", result.stdout), result.stdout
    if task:
        board = env.repo.forge("board", "--json")
        assert board.returncode == 0, board.stderr
        assert 11520 <= json.loads(board.stdout)["daily_start_to_merge"]["median_seconds"] < 11640


def test_2_board_shows_daily_median_from_merge_history(env):
    item, _, start = prepare(env)
    end = datetime.now(timezone.utc).replace(microsecond=0)
    published(env, item, merged_at=end.isoformat())
    env.repo.git("merge", "--squash", f"fix/{item}")
    env.repo.git("commit", "-qm", "Merge the change")
    second = {"kind": "fix", "branch": "fix/second", "status": "merged", "why": "A second change",
              "finished": end.isoformat(),
              "steps": [{"step": "start", "at": (end - timedelta(hours=1, minutes=12)).isoformat()}]}
    env.commit(env.repo.path, ".factory/fixes/second.json", json.dumps(second))
    events = env.repo.path / ".git/forge/events.jsonl"
    finish = {"item": "second", "event": "item finished", "at": end.isoformat()}
    with events.open("a", encoding="utf-8") as log:
        log.write(json.dumps(finish) + "\n")
    env.repo.git("push", "-q", "origin", "main")
    result = env.repo.forge("board", "--json")
    assert result.returncode == 0, result.stderr
    daily = json.loads(result.stdout)["daily_start_to_merge"]
    assert daily["date"] == end.date().isoformat()
    assert daily["median_seconds"] == ((end - start).total_seconds() + 4320) / 2
    assert daily["line"] == "Median start to merge today (UTC): 2h12m"
    second["finished"] = (end - timedelta(days=1)).isoformat()
    env.commit(env.repo.path, ".factory/fixes/second.json", json.dumps(second))
    env.repo.git("push", "-q", "origin", "main")
    published(env, item, merged_at=(end - timedelta(days=1)).isoformat())
    result = env.repo.forge("board", "--json")
    assert result.returncode == 0, result.stderr
    daily = json.loads(result.stdout)["daily_start_to_merge"]
    assert daily["median_seconds"] is None
    assert daily["line"] == "No measured merges today (UTC)"
