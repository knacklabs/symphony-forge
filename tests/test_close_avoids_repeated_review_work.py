"""Close spends one publication per run and asks before repeating unchanged work.

The real commands own review reuse, Git pushes and PR publication. Only GitHub and
Autoreview are replaced at their external edges.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from test_close import CLEAN, blocked, env, finding, run  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item
from test_land import _blocked_once_then_clean, land  # noqa: F401

STORY = "no-wasted-rounds"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_2_unchanged_blocked_work_goes_straight_to_the_owner(env, tmp_path, monkeypatch, previous):
    began = datetime(2026, 10, 15, 10, tzinfo=timezone.utc)
    monkeypatch.setenv("FORGE_NOW", began.isoformat())
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
    monkeypatch.setenv("FORGE_NOW", (began + timedelta(minutes=31)).isoformat())
    chosen = env.close(item)
    assert chosen.returncode == 1, chosen.stdout + chosen.stderr
    assert "recorded the repo's default choice: narrow" in chosen.stdout
    assert f"forge work {item}" in chosen.stderr
    assert "Nothing changed since the last review" not in chosen.stderr
    assert "Accept, narrow or split?" not in chosen.stderr
    branches = env.repo.git("branch", "--list", "fix/*")
    assert len(branches.splitlines()) == 2, branches
    again = env.close(item)
    assert "recorded the repo's default choice: narrow" not in again.stdout
    assert "Accept, narrow or split?" not in again.stderr
    assert "Nothing changed since the last review" not in again.stderr
    assert env.repo.git("branch", "--list", "fix/*") == branches
    assert len(env.review_calls()) == reviews
    assert "The repo's default answered the review loop stop" in env.repo.forge("next").stdout


@pytest.mark.parametrize("previous,existing_pr,outcome,pending_history", [
    (previous, existing, outcome, False) for previous in (False, True) for existing in (False, True)
    for outcome in ("clean", "blocked", "failed-checks")
] + [(previous, True, "clean", True) for previous in (False, True)]
  + [(previous, existing, "main-advances", False)
     for previous in (False, True) for existing in (False, True)]
  + [(False, True, "land-repair", False)])
def test_3_close_publishes_the_pull_request_body_once(
        env, tmp_path, request, previous, existing_pr, outcome, pending_history):
    if outcome == "land-repair":
        # Land reuses its command arguments across distinct close runs.
        land_env = request.getfixturevalue("land")
        module = env.repo.bin / "claude_agent_sdk/__init__.py"
        module.write_text(module.read_text("utf-8").replace(
            '        done = len(list(Path.cwd().glob("work-*.txt")))',
            '        with open(Path(__file__).resolve().parent.parent / "gh-calls.jsonl", "a", encoding="utf-8") as log:\n'
            '            log.write(json.dumps(["worker-boundary"]) + "\\n")\n'
            '        done = len(list(Path.cwd().glob("work-*.txt")))'), "utf-8")
        _blocked_once_then_clean(land_env)
        calls = env.gh.calls()
        worker = calls.index(["worker-boundary"])
        merge = next(index for index, call in enumerate(calls)
                     if call[:2] == ["pr", "view"] and call[-1] ==
                     "number,state,baseRefName,headRefName,headRefOid,title,isDraft,body")
        for close_calls in (calls[:worker], calls[worker + 1:merge]):
            publications = [call for call in close_calls
                            if call[:2] in (["pr", "create"], ["pr", "edit"]) and "--body-file" in call]
            assert len(publications) == 1, publications
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
    if outcome == "main-advances":
        _main_advances_during_checks(env, where)
        env.reviews(CLEAN, blocked(finding("P1", "New main change loses the greeting", "shared.txt", 10)))
    else:
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
    if outcome == "main-advances":
        if not existing_pr:
            assert len(env.review_calls()) == 1
            assert "The default branch changed during checks." in closed.stderr
            assert f"forge close {item}" in closed.stderr
            ready = env.gh_calls("pr", "ready")
            assert not ready or "--undo" in ready[-1], ready
            # A separate close owns the changed head and has its own publication budget.
            env.open_pr(published, draft=True)
            before = len(env.gh.calls())
            resumed = env.close(item)
            assert resumed.returncode == 1, resumed.stdout + resumed.stderr
            publications = [call for call in env.gh.calls()[before:]
                            if call[:2] in (["pr", "create"], ["pr", "edit"]) and "--body-file" in call]
            assert len(publications) == 1, publications
            published = json.loads(bodies.read_text("utf-8").splitlines()[-1])
        assert len(env.review_calls()) == 2
        assert "New main change loses the greeting" in published
        assert "The review found serious problems." in published
        assert "--undo" in env.gh_calls("pr", "ready")[-1]
        return
    if outcome == "blocked":
        assert "Greeting is missing" in published
        assert "The review found serious problems." in published
    else:
        assert "Review: clean" in published
        # A new PR starts pull_request CI: its single publication includes the review;
        # an existing PR can publish after its final CI outcome in the same run.
        if existing_pr:
            assert ("CI passed" if outcome == "clean" else "CI failed") in published


def _main_advances_during_checks(env, where):
    """GitHub moves the real remote main only when close asks for live checks."""
    shared = "First baseline line\n" + "Unchanged middle line\n" * 8 + "Last baseline line\n"
    _, preparation = env.start("main-greeting", "fix/main-greeting", ".factory/fixes/main-greeting.json",
                               {"kind": "fix", "why": "Prepare the shared greeting",
                                "done_when": "The shared greeting is available"}, {"shared.txt": shared})
    remote = env.repo.git("remote", "get-url", "origin")
    # The bare origin accepts a human merge as GitHub does; no client pushes main.
    env.repo.git("fetch", "-q", preparation.as_posix(), "HEAD:refs/heads/main", cwd=Path(remote))
    env.repo.git("fetch", "-q", "origin", "main")
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    env.commit(where, "shared.txt", shared.replace("First baseline", "Task greeting"), "Add the task greeting")
    # Both sides change a file owned by the task, far enough apart to merge cleanly.
    # A main-only new file would leave its reviewed branch diff unchanged and reuse clean.
    env.commit(preparation, "shared.txt", shared.replace("Last baseline", "New main"), "Change the main greeting")
    main = env.repo.git("rev-parse", "HEAD", cwd=preparation)
    gh = env.repo.bin / "gh"
    source = gh.read_text("utf-8")
    edge = '''
marker = here / "main-advanced"
if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"] and not marker.exists():
    subprocess.run(["git", "fetch", "-q", PREPARATION, MAIN + ":refs/heads/main"], cwd=REMOTE, check=True)
    marker.touch()
if args[:3] == ["pr", "list", "--head"] and marker.exists():
    bodies = here / "gh-bodies.jsonl"
    body = json.loads(bodies.read_text("utf-8").splitlines()[-1]) if bodies.exists() else ""
    ready = [json.loads(line) for line in (here / "gh-calls.jsonl").read_text("utf-8").splitlines()
             if json.loads(line)[:2] == ["pr", "ready"]]
    print(json.dumps([{"number": 7, "state": "OPEN", "body": body,
                       "isDraft": not ready or "--undo" in ready[-1], "mergeStateStatus": "BEHIND"}]))
    sys.exit(0)
'''
    gh.write_text(source.replace('responses = here / "gh-responses.json"',
                                "MAIN = " + json.dumps(main) + "\n" +
                                "REMOTE = " + json.dumps(Path(remote).as_posix()) + "\n" +
                                "PREPARATION = " + json.dumps(preparation.as_posix()) + "\n" + edge +
                                '\nresponses = here / "gh-responses.json"'), "utf-8")
