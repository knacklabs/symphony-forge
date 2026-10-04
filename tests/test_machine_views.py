"""Command contracts shared with the mod: board, next step, and actionable occurrences.

The old HTML/text tests do not exercise JSON, expiry across processes, or GitHub event ids.
Only GitHub is faked; commands read real repositories and their owned state fixtures.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

from test_story import setup, worktree
from test_task import story

STORY = "FORGE-MOD-1"
FIXTURE = Path(__file__).parent / "fixtures" / "board.json"


def view(repo, command, cwd=None):
    result = repo.forge(command, "--json", cwd=cwd)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def state(path, **values):
    data = json.loads(path.read_text("utf-8"))
    path.write_text(json.dumps({**data, **values}), encoding="utf-8")


def pull(number, branch, conclusion="SUCCESS", completed="2026-10-04T10:00:00Z"):
    check = {**json.loads(FIXTURE.read_text("utf-8"))["github"]["check_run"],
             "status": "IN_PROGRESS" if conclusion is None else "COMPLETED",
             "conclusion": conclusion, "completedAt": completed}
    return {"number": number, "headRefName": branch, "headRefOid": "abc123",
            "title": "Improve the page", "url": f"https://github.com/a/b/pull/{number}",
            "isDraft": False, "commits": {"nodes": [{"commit": {"statusCheckRollup": {
                "contexts": {"nodes": [check],
                             "pageInfo": {"hasNextPage": False}}}}}]}}


def github(gh, prs):
    gh.respond("api", "graphql", stdout=json.dumps(
        {"data": {"repository": {"pullRequests": {"nodes": prs}}}}))


def test_1_board_shows_stories_workers_checks_and_findings(repo, gh):
    setup(repo)
    repo.write("forge.toml", (repo.path / "forge.toml").read_text() +
               'models.build = { model = "gpt-6.1-sol", effort = "medium" }\n'
               'models.fix = { model = "gpt-6-luna", effort = "high" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-qm", "Choose build model")
    story(repo)
    repo.git("worktree", "add", str(repo.path.parent / "repo-BOARD"), "story/BOARD")
    assert view(repo, "next")["next"]["command"] == "forge task start BOARD/PAGE"
    assert repo.forge("task", "start", "BOARD/PAGE").returncode == 0
    folder = worktree(repo, "task/BOARD-PAGE")
    assert view(repo, "next")["next"]["command"] == "forge work BOARD/PAGE"
    file = folder / ".factory/stories/BOARD/tasks/PAGE.json"
    state(file, status="working", worker="codex", review={"findings": [
        {"priority": "P1", "title": "Missing empty state"},
        {"priority": "P2", "title": "Improve copy"}], "dismissals": [{"finding": 2}]})
    # A real living process holds this worker's lock; no model is asked to build the fixture.
    if os.name != "nt":
        identity = subprocess.run(["ps", "-ww", "-o", "lstart=,command=", "-p", str(os.getpid())],
                                  capture_output=True, text=True, check=True).stdout.split(None, 5)
        lock = repo.write(".git/forge/threads/task/BOARD/PAGE.lock", json.dumps(
            {"pid": os.getpid(), "started": " ".join(identity[:5]), "command": identity[5].strip()}))
    github(gh, [pull(1, "task/BOARD-PAGE")])
    result = view(repo, "board")
    assert result["version"] == repo.forge("--version").stdout.strip().split()[-1].lstrip("v")
    assert result["repo_root"] == str(repo.path.resolve())
    item = result["items"][0]
    assert item["title"] == "Board shows each story in plain English"
    child = item["children"][0]
    assert child["title"] == "The page"
    assert child["stage"] == "working"
    assert child["pr"] == {"number": 1, "checks": "pass"}
    assert child["findings"] == {"count": 1, "titles": ["Missing empty state"]}
    if os.name != "nt":
        assert child["worker"] == {"kind": "build", "model": "gpt-6.1-sol", "started_at": None}
    assert child["round"] is None
    assert all(s["started_at"] is None for s in child["stages"])
    assert view(repo, "board", folder) == result  # common repo root and cache across worktrees
    if os.name != "nt":
        # The model follows the actual round kind recorded by the Codex command boundary.
        repo.write(".git/forge/threads/task/BOARD/PAGE.log", json.dumps(
            {"kind": "Fix", "conversation": "worker", "turn": "second-round"}) + "\n")
        assert view(repo, "board")["items"][0]["children"][0]["worker"]["model"] == "gpt-6-luna"
        # A client design worker with unrecorded family must show an unknown model.
        config = folder / "forge.toml"
        config.write_text(config.read_text().replace('repo = "forge-source"', 'repo = "client"'))
        state(file, worker=None)
        assert view(repo, "board")["items"][0]["children"][0]["worker"]["model"] is None
        lock.unlink()
    gh.respond("api", "graphql", exit=1, stderr="offline")
    # Expire without sleeping or changing production time machinery.
    cache = repo.path / ".git/forge/checks-cache.json"
    state(cache, fetched_at="2000-01-01T00:00:00+00:00")
    assert view(repo, "board")["items"][0]["children"][0]["pr"]["checks"] == "unknown"
    # A landed task is finished, even though the committed state still says working.
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "-qm", "Finish the task", cwd=folder)
    repo.git("merge", "--no-ff", "-m", "Accept the task", "task/BOARD-PAGE")
    repo.git("push", "-q", "origin", "main")
    child = view(repo, "board")["items"][0]["children"][0]
    assert child["stage"] == "merged"
    assert child["next"]["command"] is None


@pytest.mark.parametrize("status,merge,command", [
    ("started", "human", "forge work polish"),
    ("ready", "human", None), ("ready", "agent", "forge merge polish"),
    ("reviewing", "human", None), ("", "human", "forge work polish")])
def test_2_next_and_board_share_the_mod_contract(repo, gh, status, merge, command):
    setup(repo, keys=())
    repo.write("forge.toml", (repo.path / "forge.toml").read_text() + f'merge = "{merge}"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-qm", "Choose merge owner")
    repo.git("push", "-q", "origin", "main")
    made = repo.forge("fix", "start", "Polish the guide", "--done", "The guide reads clearly", "--slug", "polish")
    assert made.returncode == 0, made.stderr
    folder = worktree(repo, "fix/polish")
    state(folder / ".factory/fixes/polish.json", status=status)
    github(gh, [])
    plain = repo.forge("next").stdout
    result = view(repo, "next")
    assert result["next"]["command"] == command
    assert result["next"]["line"] in plain.splitlines()
    assert not result["next"]["line"].startswith("Next: ")
    row = view(repo, "board")["items"][0]
    assert row["stage"] == (status or "unknown")
    assert row["next"]["command"] == command
    # Shared mod fixture checks transport types and required fields, not private records.
    fixture = json.loads(FIXTURE.read_text("utf-8"))
    def contract(actual, example):
        if isinstance(example, dict):
            assert isinstance(actual, dict)
            for key, value in example.items():
                contract(actual[key], value)
        elif isinstance(example, list):
            assert isinstance(actual, list)
            if example:
                for value in actual:
                    contract(value, example[0])
        elif example is not None:
            assert isinstance(actual, type(example))
    contract(result, fixture["next"])
    contract(view(repo, "board"), fixture["board"])
    assert [s["name"] for s in row["stages"]] == [s["name"] for s in fixture["board"]["items"][0]["stages"]]
    if status == "started":
        # RUNS' future producer contract: current round only, real durations, skipped docs tests.
        state(folder / ".factory/fixes/polish.json", round=2)
        repo.write(".git/forge/timings.jsonl", "\n".join(json.dumps(r) for r in [
            {"item": "polish", "round": 1, "step": "worker round", "seconds": 90,
             "start": "2026-10-04T09:00:00Z", "end": "2026-10-04T09:01:30Z", "outcome": "completed"},
            {"item": "polish", "round": 2, "step": "worker round", "seconds": 10,
             "start": "2026-10-04T10:00:00Z", "end": "2026-10-04T10:00:10Z", "outcome": "completed"},
            {"item": "polish", "round": 2, "step": "test", "seconds": 0,
             "start": None, "end": None, "outcome": "skipped"},
            {"item": "polish", "round": 2, "step": "review", "seconds": None,
             "start": "2026-10-04T10:01:00Z", "end": None, "outcome": "running"}]))
        row = view(repo, "board")["items"][0]
        assert row["round"] == 2
        assert row["stages"][0] == {"name": "Build", "status": "pass", "seconds": 10,
                                     "started_at": "2026-10-04T10:00:00Z", "ended_at": "2026-10-04T10:00:10Z"}
        assert row["stages"][1]["status"] == "skipped"
        assert row["stages"][2] == {"name": "Review", "status": "running", "seconds": None,
                                     "started_at": "2026-10-04T10:01:00Z", "ended_at": None}
        assert row["total_seconds"] == 100


def test_3_board_reports_github_occurrences_after_cache_expiry(repo, gh, monkeypatch):
    setup(repo, keys=())
    assert view(repo, "board")["items"] == []
    initial_calls = len([c for c in gh.calls() if c[:2] == ["api", "graphql"]])
    for name in ("first", "second", "older"):
        made = repo.forge("fix", "start", name, "--done", "Reads clearly", "--slug", name)
        assert made.returncode == 0, made.stderr
    prs = [pull(n, "fix/first" if n == 30 else "fix/second" if n == 29 else f"fix/other-{n}")
           for n in range(30, 5, -1)]
    github(gh, prs)
    gh.respond("pr", "list", stdout=json.dumps([
        {"number": n, "headRefName": "fix/older" if n == 1 else f"fix/other-{n}"}
        for n in range(5, 0, -1)]))
    monkeypatch.setenv("FORGE_NOW", "2026-10-04T10:00:00+00:00")
    first = view(repo, "board")
    assert {r["id"]: r["pr"]["checks"] for r in first["items"]} == {
        "first": "pass", "second": "pass", "older": "unknown"}
    prs[0] = pull(30, "fix/first", "FAILURE")
    github(gh, prs)
    monkeypatch.setenv("FORGE_NOW", "2026-10-04T10:00:59+00:00")
    assert view(repo, "board") == first
    # The HTML board uses the same cache; it must not refresh the open checks early.
    html = repo.forge("board", "--out", str(repo.path / ".git/forge/cache-board.html"))
    assert html.returncode == 0, html.stderr
    assert len([c for c in gh.calls() if c[:2] == ["api", "graphql"]]) == initial_calls + 1
    monkeypatch.setenv("FORGE_NOW", "2026-10-04T10:01:00+00:00")
    rows = {r["id"]: r for r in view(repo, "board")["items"]}
    assert rows["first"]["pr"]["checks"] == "fail"
    event = rows["first"]["occurrences"][0]
    assert event["id"] == "check-run:111371488290:2026-10-04T10:00:00Z"
    assert rows["first"]["next"]["command"] == "forge work first"
    assert rows["second"]["next"]["command"] == "forge work second"
    # A later completion under the same id is a different occurrence; status ids are GitHub's.
    prs[0] = pull(30, "fix/first", None, None)
    github(gh, prs)
    monkeypatch.setenv("FORGE_NOW", "2026-10-04T10:02:00+00:00")
    running = {r["id"]: r for r in view(repo, "board")["items"]}["first"]
    assert running["pr"]["checks"] == "running" and running["occurrences"] == []
    prs[0] = pull(30, "fix/first", "FAILURE", "2026-10-04T10:03:00Z")
    contexts = prs[0]["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]
    contexts["nodes"].append(json.loads(FIXTURE.read_text("utf-8"))["github"]["commit_status"])
    github(gh, prs)
    monkeypatch.setenv("FORGE_NOW", "2026-10-04T10:03:00+00:00")
    events = {r["id"]: r for r in view(repo, "board")["items"]}["first"]["occurrences"]
    assert {e["id"] for e in events} == {"check-run:111371488290:2026-10-04T10:03:00Z", "status:SC_kwDNIULPAAAADOrMkdw"}
    contexts["nodes"][0]["databaseId"] = 111371488291
    contexts["nodes"][1]["id"] = "SC_kwDNIULPAAAADOokTrg"
    github(gh, prs)
    monkeypatch.setenv("FORGE_NOW", "2026-10-04T10:04:00+00:00")
    events = {r["id"]: r for r in view(repo, "board")["items"]}["first"]["occurrences"]
    assert {e["id"] for e in events} == {"check-run:111371488291:2026-10-04T10:03:00Z", "status:SC_kwDNIULPAAAADOokTrg"}
    calls = [c for c in gh.calls() if c[:2] == ["api", "graphql"]]
    assert len(calls) == initial_calls + 5
    assert "first: 25" in " ".join(calls[-1]) and "CREATED_AT" in " ".join(calls[-1])
