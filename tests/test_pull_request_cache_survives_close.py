"""Closing work keeps the shared minute cache; next fetches default settings once per run."""
import json
import os
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone

import pytest

from conftest import _install
from test_board_github_once import lists, row
from test_close import body, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "keep-pr-cache"
NOW = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)


def count_git(repo):
    real = shutil.which("git")
    _install(repo.bin, "git", f'''#!{sys.executable}
import pathlib, subprocess, sys
from json_log import append_json
append_json(pathlib.Path(__file__).with_name("git-calls.jsonl"), sys.argv[1:])
sys.exit(subprocess.run([{json.dumps(real)}, *sys.argv[1:]]).returncode)
''')
    log = repo.bin / "git-calls.jsonl"
    return lambda: [json.loads(line) for line in log.read_text("utf-8").splitlines()] if log.exists() else []


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_close_from_a_worktree_keeps_cached_lists_until_the_minute_expires(env, monkeypatch, previous):
    client(env, previous)
    monkeypatch.setenv("FORGE_NOW", NOW.isoformat())
    item, where = env.start_fix()
    git_calls = count_git(env.repo)
    warmed = env.repo.forge("next", "--json")
    assert warmed.returncode == 0, warmed.stderr
    assert len(lists(env)) == 8
    assert row(json.loads(warmed.stdout), item)["pr"]["number"] is None

    # The old contract invalidated every worktree's lists on create, edit and ready.
    # Close still publishes each change, but cached readers see it at the next expiry.
    for existing in (False, True):
        if existing:
            env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
        before = len(git_calls()), len(env.gh.calls())
        started = time.monotonic()
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert env.gh_calls("pr", "edit")
        shown = env.repo.forge("next", "--json", cwd=where if existing else env.repo.path)
        elapsed = time.monotonic() - started
        assert shown.returncode == 0, shown.stderr
        assert row(json.loads(shown.stdout), item)["pr"]["number"] is None
        assert len(lists(env)) == 8, "close discarded the shared pull request lists"
        assert len(git_calls()) - before[0] <= 500
        assert len(env.gh.calls()) - before[1] <= 40
        assert elapsed < (180 if os.name == "nt" else 90), elapsed
    assert env.gh_calls("pr", "create") and env.gh_calls("pr", "ready")

    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([{
        "number": 7, "headRefName": f"fix/{item}", "state": "OPEN", "title": "Published greeting",
        "body": "", "isDraft": False, "url": "https://github.com/acme/shop/pull/7"}]))
    monkeypatch.setenv("FORGE_NOW", (NOW + timedelta(seconds=60)).isoformat())
    refreshed = env.repo.forge("next", "--json")
    assert refreshed.returncode == 0, refreshed.stderr
    assert len(lists(env)) == 16
    assert row(json.loads(refreshed.stdout), item)["pr"]["number"] == 7


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_2_next_fetches_default_settings_once_and_fetches_again_on_the_next_run(env, monkeypatch, previous):
    client(env, previous)
    monkeypatch.setenv("FORGE_NOW", NOW.isoformat())
    # Both ready-to-merge advice and the demo check read the default branch's settings.
    env.commit(env.repo.path, "Dockerfile", "FROM scratch\n")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
    git_calls = count_git(env.repo)
    for _ in range(2):
        before = len(git_calls()), len(env.gh.calls())
        started = time.monotonic()
        shown = env.repo.forge("next")
        elapsed = time.monotonic() - started
        assert shown.returncode == 0, shown.stderr
        assert item in shown.stdout and "ready" in shown.stdout, shown.stdout
        calls = git_calls()[before[0]:]
        fetches = [call for call in calls if call[0] == "fetch"]
        assert fetches == [["fetch", "-q", "origin", "main"]], fetches
        assert len(calls) <= 180
        assert len(env.gh.calls()) - before[1] <= 12
        assert elapsed < (90 if os.name == "nt" else 30), elapsed
