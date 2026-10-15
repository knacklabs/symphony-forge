"""Close spends one publication per run and asks before repeating unchanged work.

The real commands own review reuse, Git pushes and PR publication. Only GitHub and
Autoreview are replaced at their external edges.
"""
import json
import re
from pathlib import Path

import pytest

from test_close import CLEAN, blocked, env, finding, run  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item
from test_land import _blocked_once_then_clean, land  # noqa: F401

STORY = "no-wasted-rounds"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_2_unchanged_blocked_work_goes_straight_to_the_owner(env, tmp_path, monkeypatch, previous):
    item, where = client_item(env, tmp_path, previous)
    env.reviews(blocked(finding("P1", "Greeting is missing")))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    env.open_pr("", draft=True)
    reviews, github = len(env.review_calls()), len(env.gh.calls())
    trace = tmp_path / "git-trace.jsonl"
    monkeypatch.setenv("GIT_TRACE2_EVENT", trace.as_posix())

    stopped = env.close(item)

    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "Nothing changed since the last review" in stopped.stderr
    assert "Greeting is missing" in stopped.stderr
    assert "Accept, narrow or split?" in stopped.stderr
    assert f'forge close {item} --resolve <narrow|split|accept>' in stopped.stderr
    assert len(env.review_calls()) == reviews
    assert not any(call[:2] in (["pr", "create"], ["pr", "edit"])
                   for call in env.gh.calls()[github:])
    events = [json.loads(line) for line in trace.read_text("utf-8").splitlines()]
    assert not any("push" in event.get("argv", []) for event in events if event["event"] == "start")


@pytest.mark.parametrize("previous,existing_pr,outcome,pending_history", [
    (previous, existing, outcome, False) for previous in (False, True) for existing in (False, True)
    for outcome in ("clean", "blocked", "failed-checks")
] + [(previous, True, "clean", True) for previous in (False, True)]
  + [(False, True, "land-repair", False)])
def test_3_close_publishes_the_pull_request_body_once(
        env, tmp_path, request, previous, existing_pr, outcome, pending_history):
    if outcome == "land-repair":
        # Land reuses its command arguments across distinct close runs.
        _blocked_once_then_clean(request.getfixturevalue("land"))
        bodies = [json.loads(line) for line in
                  (env.repo.bin / "gh-bodies.jsonl").read_text("utf-8").splitlines()]
        assert any("Saving drops the greeting" in body for body in bodies)
        assert "Review: clean" in bodies[-1]
        return
    item, where = client_item(env, tmp_path, previous)
    if pending_history:
        # The first real close supplies actual history, not a fabricated receipt.
        first = env.close(item)
        assert first.returncode == 0, first.stdout + first.stderr
        bodies = env.repo.bin / "gh-bodies.jsonl"
        old_body = json.loads(bodies.read_text("utf-8").splitlines()[-1])
        stripped = re.sub(r"<!-- forge:time-record \{.*?\} -->\n?", "", old_body, flags=re.S)
        assert stripped != old_body
        env.open_pr(stripped, draft=False)
        branch = env.repo.git("branch", "--show-current", cwd=where)
        env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([
            {"number": 7, "state": "OPEN", "headRefName": branch, "body": stripped}]))
        env.repo.git("push", "-q", "origin", "HEAD:refs/pull/7/head", cwd=where)
        common = Path(env.repo.git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=where))
        (common / "forge/backfill-pending").touch()
        env.commit(where, "app.py", "print('greeting with another change')\n")
    elif existing_pr:
        env.open_pr("", draft=True)
    env.reviews(blocked(finding("P1", "Greeting is missing")) if outcome == "blocked" else CLEAN)
    if outcome == "failed-checks":
        env.checks([run("tests", "failure"), run("forge-pr-check")])
    before = len(env.gh.calls())
    bodies = env.repo.bin / "gh-bodies.jsonl"
    old_bodies = len(bodies.read_text("utf-8").splitlines()) if bodies.exists() else 0

    closed = env.close(item)

    assert closed.returncode == (0 if outcome == "clean" else 1), closed.stdout + closed.stderr
    publications = [call for call in env.gh.calls()[before:]
                    if call[:2] in (["pr", "create"], ["pr", "edit"]) and "--body-file" in call]
    assert len(publications) == 1, publications
    [published] = [json.loads(line) for line in bodies.read_text("utf-8").splitlines()[old_bodies:]]
    if outcome == "blocked":
        assert "Greeting is missing" in published
        assert "The review found serious problems." in published
    else:
        assert "Review: clean" in published
        # A new PR starts pull_request CI: its single publication includes the review;
        # an existing PR can publish after its final CI outcome in the same run.
        if existing_pr:
            assert ("CI passed" if outcome == "clean" else "CI failed") in published
