"""Command proof for elapsed merge time and the daily board figure.

Audit: exact output, shared history, batch land, mixed item kinds, missing starts
and a stale PR cache are independent gaps in the earlier command cases. Only
external services are fake. No production seam is needed.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from test_close import STORY_DOC, body, env  # noqa: F401
from test_last_task_records_story_outcome import github_merge
from test_queue_land_all import _fix, client  # noqa: F401
from test_train_land_all import train  # noqa: F401

STORY = "FIX-START-TO-MERGE-TIME"


def history(env, item, start, ci=False):
    folder = env.repo.path / ".git/forge"
    folder.mkdir(exist_ok=True)
    events = [
        {"item": item, "event": "work phase", "phase": "building", "round": 1, "at": start.isoformat()},
        {"item": item, "event": "owner wait start", "reason": "merge", "id": item,
         "round": 1, "at": (start + timedelta(minutes=1)).isoformat()},
    ]
    if ci:
        events.append({"item": item, "event": "owner wait end", "wait_id": item,
                       "at": (start + timedelta(minutes=11)).isoformat()})
        with (folder / "timings.jsonl").open("a", encoding="utf-8") as log:
            log.write(json.dumps({"item": item, "step": "CI wait", "round": 1, "outcome": "passed",
                                  "start": (start + timedelta(minutes=11)).isoformat(), "seconds": 7200}) + "\n")
    with (folder / "events.jsonl").open("a", encoding="utf-8") as log:
        log.writelines(json.dumps(event) + "\n" for event in events)


def prepare(env, task=False, ci=False):
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    start = (datetime.now(timezone.utc) - timedelta(hours=3, minutes=12)).replace(microsecond=0)
    if task:
        item, where = env.start_approved_task(STORY_DOC)
        path = ".factory/stories/SHOP/tasks/T1.json"
        state = json.loads((where / path).read_text("utf-8"))
        env.commit(where, path, json.dumps({**state, "steps": [{"step": "start", "at": start.isoformat()}]}))
    else:
        item, where = env.start_fix(round=1, steps=[{"step": "start", "at": start.isoformat()}])
    history(env, item, start, ci)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    return item, where, start


def merge_time(repo, path):
    return datetime.fromisoformat(repo.git("log", "--first-parent", "--diff-filter=A", "-1",
                                           "--format=%cI", "origin/main", "--", path)).astimezone(timezone.utc)


def line(item, start, end, cause):
    hours, minutes = divmod(int((end - start).total_seconds() // 60), 60)
    return (f"Merged {item}: started {start.isoformat()}, merged {end.isoformat()}, "
            f"{hours}h{minutes}m start to merge; biggest wait: {cause}")


@pytest.mark.parametrize("command,task,ci", [("merge", False, False), ("land", False, True), ("merge", True, True)])
def test_1_merge_and_land_print_start_to_merge_time(env, command, task, ci):
    item, _, start = prepare(env, task, ci)
    published = body(env.gh_calls("pr", "edit")[-1])
    github_merge(env, "task/SHOP-T1" if task else f"fix/{item}")
    gh = env.repo.bin / "gh"
    gh.write_text(gh.read_text("utf-8").replace('"isDraft": False', f'"isDraft": False, "body": {published!r}'), "utf-8")
    # This machine retains the published record, but none of the other machine's local observations.
    for name in ("events", "timings"):
        (env.repo.path / f".git/forge/{name}.jsonl").write_text("", "utf-8")
    result = env.repo.forge(command, item)
    assert result.returncode == 0, result.stdout + result.stderr
    path = ".factory/stories/SHOP/tasks/T1.json" if task else f".factory/fixes/{item}.json"
    end = merge_time(env.repo, path)
    assert line(item, start, end, "waiting for CI" if ci else "waiting for the owner") in result.stdout.splitlines()
    if task:
        board = env.repo.forge("board", "--json")
        assert board.returncode == 0, board.stderr
        assert json.loads(board.stdout)["daily_start_to_merge"]["median_seconds"] == (end - start).total_seconds()


@pytest.mark.parametrize("stale", [False, True], ids=["merged-pr", "cached-open-pr"])
def test_2_board_shows_daily_median_from_merge_history(env, stale):
    item, _, start = prepare(env)
    published = body(env.gh_calls("pr", "edit")[-1])
    env.repo.git("merge", "--squash", f"fix/{item}")
    env.repo.git("commit", "-qm", "Merge the fix")
    fix_end = datetime.fromisoformat(env.repo.git("log", "-1", "--format=%cI")).astimezone(timezone.utc)
    part_start = fix_end - timedelta(hours=1, minutes=12)
    part_path = ".factory/stories/SHOP/tasks/T1.json"
    part = {"branch": "task/SHOP-T1", "status": "merged", "steps": [{"step": "start", "at": part_start.isoformat()}]}
    env.commit(env.repo.path, "plans/SHOP.md", STORY_DOC)
    env.commit(env.repo.path, ".factory/stories/SHOP/story.json", json.dumps({"status": "approved", "title": "Shoppers can save a basket"}))
    env.commit(env.repo.path, part_path, json.dumps(part))
    part_end = datetime.fromisoformat(env.repo.git("log", "-1", "--format=%cI")).astimezone(timezone.utc)
    env.commit(env.repo.path, ".factory/fixes/unmeasured.json", json.dumps({
        "kind": "fix", "branch": "fix/unmeasured", "status": "merged", "why": "An older change with no start"}))
    env.repo.git("push", "-q", "origin", "main")
    for name in ("events", "timings"):
        (env.repo.path / f".git/forge/{name}.jsonl").write_text("", "utf-8")
    prs = [
        {"number": 7, "headRefName": f"fix/{item}", "state": "MERGED", "mergedAt": fix_end.isoformat(), "body": published},
        {"number": 8, "headRefName": "task/SHOP-T1", "state": "OPEN" if stale else "MERGED",
         "mergedAt": None if stale else part_end.isoformat(), "body": ""},
    ]
    env.gh.respond("pr", "list", stdout=json.dumps(prs))
    result = env.repo.forge("board", "--json")
    assert result.returncode == 0, result.stderr
    board = json.loads(result.stdout)
    unknown = next(row for row in board["items"] if row["id"] == "unmeasured")
    assert unknown["merged_at"][:10] == fix_end.date().isoformat() and unknown["total_seconds"] is None
    daily = board["daily_start_to_merge"]
    assert daily["date"] == fix_end.date().isoformat()
    assert daily["median_seconds"] == ((fix_end - start).total_seconds() + (part_end - part_start).total_seconds()) / 2
    assert daily["line"] == "Median start to merge today (UTC): 2h12m"
    # Both measured changes move to yesterday; the unmeasured merge remains today.
    part["finished"] = (part_end - timedelta(days=1)).isoformat()
    env.commit(env.repo.path, part_path, json.dumps(part))
    env.repo.git("push", "-q", "origin", "main")
    for pr, end in zip(prs, (fix_end, part_end)):
        pr.update(state="MERGED", mergedAt=(end - timedelta(days=1)).isoformat())
    env.gh.respond("pr", "list", stdout=json.dumps(prs))
    for cache in env.tmp.rglob("prs-cache.json"):
        cache.unlink()
    result = env.repo.forge("board", "--json")
    assert result.returncode == 0, result.stderr
    daily = json.loads(result.stdout)["daily_start_to_merge"]
    assert daily["median_seconds"] is None
    assert daily["line"] == "No measured merges today (UTC)"


def test_3_each_item_in_a_named_land_batch_prints_its_measurement(train, monkeypatch):
    env = train
    starts = {}
    for day, slug in enumerate(("aa", "bb"), 1):
        start = (datetime.now(timezone.utc) - timedelta(hours=3, minutes=12)).replace(microsecond=123456)
        _fix(env, monkeypatch, slug, day, {f"{slug}.py": f"print('{slug}')\n"}, status="working",
             steps=[{"step": "start", "at": start.isoformat()}])
        history(env, slug, start, ci=True)
        closed = env.repo.forge("close", slug)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        starts[slug] = start
    result = env.repo.forge("land", "aa", "bb", timeout=600)
    assert result.returncode == 0, result.stdout + result.stderr
    for slug in starts:
        end = merge_time(env.repo, f".factory/fixes/{slug}.json")
        matches = [shown.removeprefix(f"{slug}: ") for shown in result.stdout.splitlines()
                   if shown.removeprefix(f"{slug}: ").startswith(f"Merged {slug}: started ")]
        assert len(matches) == 1, result.stdout
        assert matches[0] == line(slug, starts[slug], end, "waiting for CI")
