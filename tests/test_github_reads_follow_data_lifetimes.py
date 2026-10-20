"""GitHub reads follow the age of the data, and concurrent readers share a fetch."""
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from conftest import _install
from test_board_counts import github
from test_machine_views_recent_finished_items import client, finished_fix, landed
from test_story import DOC

STORY = "github-cache-lifetimes"
NOW = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)


def setup(repo, gh, monkeypatch, history):
    monkeypatch.setenv("FORGE_NOW", NOW.isoformat())
    client(repo, gh, history)
    gh.respond("api", "--paginate", stdout="")
    gh.respond("api", "user", stdout="builder\n")
    gh.respond("api", "repos/{owner}/{repo}/actions/runs", stdout='{"workflow_runs": []}')
    # An unfinished story retains a part older than the six-week window.
    old = (NOW - timedelta(weeks=9)).isoformat()
    landed(repo, monkeypatch, old, {
        ".factory/stories/LIVE/story.json": {"status": "approved", "title": "Live story"},
        "plans/LIVE.md": DOC,
        ".factory/stories/LIVE/tasks/SAVE.json": {"status": "merged", "branch": "task/LIVE-SAVE"},
        **{f".factory/fixes/done-{n}.json": finished_fix(f"done-{n}") for n in range(24)},
    })


def read(repo):
    shown = repo.forge("next", "--json")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    data = json.loads(shown.stdout)
    assert "LIVE" in {row["id"] for row in data["items"]}
    return data


def reads(calls):
    lists = [call for call in calls if call[:2] == ["pr", "list"]]
    return (
        sum("open" in call for call in lists),
        sum(any(arg.startswith("merged:") and not arg.startswith("merged:*") for arg in call) for call in lists),
        sum(any(arg.startswith("merged:*") for arg in call) for call in lists),
        sum(call[:2] == ["api", "--paginate"] for call in calls),
        sum("repos/{owner}/{repo}/actions/runs" in call for call in calls),
    )


@pytest.mark.platform
@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_next_reuses_github_until_each_data_lifetime_ends(repo, gh, monkeypatch, history):
    # Old contract refreshed all seven weeks and history each minute. The new
    # contract refreshes only the open list/current week, then schedules, then history.
    setup(repo, gh, monkeypatch, history)
    before = len(gh.calls())
    read(repo)
    assert reads(gh.calls()[before:]) == (1, 7, 1, 1, 1)

    real_git = shutil.which("git")
    git_log = repo.bin / "git-calls.jsonl"
    _install(repo.bin, "git", f'''#!{sys.executable}
import subprocess, sys
from pathlib import Path
from json_log import append_json
append_json(Path({json.dumps(str(git_log))}), sys.argv[1:])
sys.exit(subprocess.run([{json.dumps(real_git)}, *sys.argv[1:]]).returncode)
''')
    before = len(gh.calls())
    start = time.monotonic()
    read(repo)
    elapsed = time.monotonic() - start
    assert gh.calls()[before:] == [], "a warm next contacted GitHub"
    assert len(git_log.read_text("utf-8").splitlines()) <= 100
    assert elapsed < (30 if os.name == "nt" else 10), f"warm next took {elapsed:.2f}s"

    # Lifetimes are elapsed seconds from each fetch, not calendar boundaries.
    # The open/current-week lists live 60 seconds, schedules 600 seconds,
    # and past weeks, older merges and known issues 86400 seconds.
    for seconds, expected in [(59, (0, 0, 0, 0, 0)), (60, (1, 1, 0, 0, 0)),
                              (599, (1, 1, 0, 0, 0)), (600, (0, 0, 0, 0, 1)),
                              (86400, (1, 7, 1, 1, 1)), (86401, (0, 0, 0, 0, 0))]:
        monkeypatch.setenv("FORGE_NOW", (NOW + timedelta(seconds=seconds)).isoformat())
        before = len(gh.calls())
        read(repo)
        assert reads(gh.calls()[before:]) == expected, seconds


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_2_concurrent_next_readers_share_each_github_fetch(repo, gh, monkeypatch, history):
    setup(repo, gh, monkeypatch, history)
    before = len(gh.calls())
    with ThreadPoolExecutor(2) as pool:
        views = list(pool.map(lambda _: read(repo), range(2)))
    assert reads(gh.calls()[before:]) == (1, 7, 1, 1, 1)
    assert views[0]["team"] == views[1]["team"]


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_3_monday_keeps_parts_from_the_week_leaving_the_weekly_window(repo, gh, monkeypatch, history):
    setup(repo, gh, monkeypatch, history)
    # Another archived part forces the older-list lookup before the rollover.
    landed(repo, monkeypatch, (NOW - timedelta(weeks=9)).isoformat(), {
        ".factory/stories/LIVE/tasks/ANCIENT.json": {
            "status": "merged", "branch": "task/LIVE-ANCIENT"},
    })
    # Sunday includes October 5-11 in its weekly lists; Monday needs that part
    # from the older listing, even though Sunday's older listing is still young.
    sunday = datetime(2026, 11, 22, 23, 58, tzinfo=timezone.utc)
    events = [
        {"id": "save-phase", "event": "work phase", "phase": "building", "round": 1,
         "at": "2026-10-07T10:00:00+00:00"},
        {"id": "save-start", "event": "run start", "kind": "worker", "round": 1,
         "at": "2026-10-07T10:00:00+00:00"},
        {"id": "save-end", "event": "run end", "kind": "worker", "round": 1,
         "run_id": "save-start", "at": "2026-10-07T11:00:00+00:00"},
    ]
    published = ("<!-- forge:begin -->\n<!-- forge:time-record "
                 + json.dumps({"events": events}) + " -->\n<!-- forge:end -->")
    github(SimpleNamespace(repo=repo, gh=gh), [{
        "number": 7, "headRefName": "task/LIVE-SAVE", "state": "MERGED", "body": published,
        "title": "Save baskets", "mergedAt": "2026-10-07T11:00:00+00:00",
        "files": [{"path": ".factory/stories/LIVE/tasks/SAVE.json"}],
    }])
    for at in (sunday, sunday + timedelta(minutes=3), sunday + timedelta(minutes=5)):
        monkeypatch.setenv("FORGE_NOW", at.isoformat())
        shown = read(repo)
        live = next(row for row in shown["items"] if row["id"] == "LIVE")
        assert live["time_breakdown"]["working"] == 3600, at
    older = [call[call.index("--search") + 1] for call in gh.calls()
             if any(arg.startswith("merged:*") for arg in call)]
    assert older == ["merged:*..2026-10-04", "merged:*..2026-10-11"]
