"""Command contracts shared with the mod: board, next step, and actionable occurrences.

The old HTML/text tests do not exercise JSON, expiry across processes, or GitHub event ids.
Only GitHub is faked; commands read real repositories and their owned state fixtures.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_story import setup, worktree
from test_task import story
from conftest import ROOT
from test_close import GREEN, STORY_DOC, env  # noqa: F401
from test_last_task_records_story_outcome import github_merge

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


@pytest.mark.parametrize("context", [None, "commit status", "check start"])
def test_1_board_shows_stories_workers_checks_and_findings(repo, gh, context):
    if context is not None:
        _successful_checks_make_json_and_html_boards_ready(repo, gh, context)
        return
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
    made = repo.forge("fix", "start", "Polish the guide", "--done", "The guide reads clearly", "--slug", "polish")
    assert made.returncode == 0, made.stderr
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
    github(gh, [pull(1, "task/BOARD-PAGE"), pull(2, "fix/polish")])
    result = view(repo, "board")
    assert result["version"] == repo.forge("--version").stdout.strip().split()[-1].lstrip("v")
    assert result["repo_root"] == str(repo.path.resolve())
    rows = {r["id"]: r for r in result["items"]}
    assert set(rows) == {"BOARD", "polish"}
    assert rows["polish"]["title"] == "Polish the guide"
    assert rows["polish"]["kind"] == "fix"
    assert rows["polish"]["pr"] == {"number": 2, "checks": "pass"}
    item = rows["BOARD"]
    assert item["title"] == "Board shows each story in plain English"
    assert item["approval"] is None
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
        assert next(r for r in view(repo, "board")["items"] if r["id"] == "BOARD")["children"][0]["worker"]["model"] == "gpt-6-luna"
        # A client design worker with unrecorded family must show an unknown model.
        config = folder / "forge.toml"
        config.write_text(config.read_text().replace('repo = "forge-source"', 'repo = "client"'))
        state(file, worker=None)
        assert next(r for r in view(repo, "board")["items"] if r["id"] == "BOARD")["children"][0]["worker"]["model"] is None
    gh.respond("api", "graphql", exit=1, stderr="offline")
    # Expire without sleeping or changing production time machinery.
    cache = repo.path / ".git/forge/checks-cache.json"
    state(cache, fetched_at="2000-01-01T00:00:00+00:00")
    offline = {r["id"]: r for r in view(repo, "board")["items"]}
    assert set(offline) == {"BOARD", "polish"}
    assert offline["BOARD"]["children"][0]["pr"]["checks"] == "unknown"
    assert offline["polish"]["pr"]["checks"] == "unknown"
    assert offline["BOARD"]["title"] == item["title"]
    assert offline["polish"]["title"] == rows["polish"]["title"]
    if os.name != "nt":
        assert offline["BOARD"]["children"][0]["worker"] is not None
        lock.unlink()
    # A landed task is finished, even though the committed state still says working.
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "-qm", "Finish the task", cwd=folder)
    repo.git("merge", "--no-ff", "-m", "Accept the task", "task/BOARD-PAGE")
    repo.git("push", "-q", "origin", "main")
    child = next(r for r in view(repo, "board")["items"] if r["id"] == "BOARD")["children"][0]
    assert child["stage"] == "merged"
    assert child["next"]["command"] is None


def _successful_checks_make_json_and_html_boards_ready(repo, gh, context):
    # The raw GraphQL rollup replaced gh's exported timestamps. Both board consumers
    # must retain readiness, including a successful CheckRun without a completion time.
    setup(repo, keys=())
    repo.write("forge.toml", (repo.path / "forge.toml").read_text() + 'checks = ["forge-pr-check"]\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-qm", "Choose required check")
    repo.git("push", "-q", "origin", "main")
    story(repo)
    assert repo.forge("task", "start", "BOARD/PAGE").returncode == 0
    task_folder = worktree(repo, "task/BOARD-PAGE")
    state(task_folder / ".factory/stories/BOARD/tasks/PAGE.json", status="waiting for checks")
    made = repo.forge("fix", "start", "Polish the guide", "--done", "The guide reads clearly", "--slug", "polish")
    assert made.returncode == 0, made.stderr
    state(worktree(repo, "fix/polish") / ".factory/fixes/polish.json", status="waiting for checks")
    pr = pull(1, "fix/polish")
    pr["headRefOid"] = repo.git("rev-parse", "fix/polish")
    fixture = json.loads(FIXTURE.read_text("utf-8"))["github"]
    check = ({**fixture["commit_status"], "context": "forge-pr-check", "state": "SUCCESS"}
             if context == "commit status" else
             {**fixture["check_run"], "conclusion": "SUCCESS", "completedAt": None,
              "startedAt": "2026-10-04T10:00:00Z"})
    pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"] = [check]
    task_pr = {**pr, "number": 2, "headRefName": "task/BOARD-PAGE",
               "headRefOid": repo.git("rev-parse", "task/BOARD-PAGE"),
               "url": "https://github.com/a/b/pull/2"}
    github(gh, [pr, task_pr])
    gh.respond("pr", "list", "--state", "all", stdout=json.dumps([{**pr, "state": "OPEN"}]))
    rows = {r["id"]: r for r in view(repo, "board")["items"]}
    row = rows["polish"]
    assert row["pr"]["checks"] == "pass"
    assert row["stage"] == "ready"
    assert rows["BOARD"]["children"][0]["stage"] == "ready"
    assert row["next"] == {"command": None, "line": "Polish the guide is ready to merge: https://github.com/a/b/pull/1"}
    page = repo.path / ".git/forge/ready-board.html"
    result = repo.forge("board", "--out", str(page))
    assert result.returncode == 0, result.stderr
    assert "Ready to merge" in page.read_text("utf-8")
    # The GitHub request must ask for the fallback; a canned response cannot prove that.
    query = next(c for c in gh.calls() if c[:2] == ["api", "graphql"])
    assert "startedAt" in " ".join(query)
    assert "\n" not in query[-1], "Windows .cmd shims must receive the whole query on one line"
    # The whole result must pass on this head, including checks not named in config.
    optional = {**fixture["check_run"], "name": "optional preview"}
    for draft, nodes, more, stale in (
            (True, [check], False, False), (False, [], False, False),
            (False, [check, optional], False, False),
            (False, [check, {**optional, "status": "IN_PROGRESS", "conclusion": None}], False, False),
            (False, [check, {**optional, "status": "IN_PROGRESS", "conclusion": "SUCCESS"}], False, False),
            (False, [check], True, False), (False, [check], False, True)):
        pr["isDraft"] = task_pr["isDraft"] = draft
        contexts = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]
        contexts["nodes"] = nodes
        contexts["pageInfo"]["hasNextPage"] = more
        if stale:
            # A fresh fetch still describes the previous push after a local commit.
            for folder in (worktree(repo, "fix/polish"), task_folder):
                repo.git("commit", "--allow-empty", "-qm", "Change the branch head", cwd=folder)
        github(gh, [pr, task_pr])
        state(repo.path / ".git/forge/checks-cache.json", fetched_at="2000-01-01T00:00:00+00:00")
        rows = {r["id"]: r for r in view(repo, "board")["items"]}
        assert rows["polish"]["stage"] == "waiting for checks"
        assert rows["BOARD"]["children"][0]["stage"] == "waiting for checks"
        for row in (rows["polish"], rows["BOARD"]["children"][0]):
            assert "ready to merge" not in row["next"]["line"]
            assert "checks passed" not in row["next"]["line"]
        assert "ready to merge" not in view(repo, "next")["next"]["line"]


def _skipped_checks_fail_only_when_required(repo, gh, conclusion, required):
    # Match the existing check gate, including required matrix variants; optional skips
    # must remain harmless. Existing occurrence coverage exercises FAILURE only.
    setup(repo, keys=())
    repo.write("forge.toml", (repo.path / "forge.toml").read_text() + 'checks = ["forge-pr-check"]\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-qm", "Choose required check")
    repo.git("push", "-q", "origin", "main")
    made = repo.forge("fix", "start", "Polish the guide", "--done", "The guide reads clearly", "--slug", "polish")
    assert made.returncode == 0, made.stderr
    pr = pull(1, "fix/polish")
    nodes = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"]
    name = "forge-pr-check (macos)" if required else "optional preview"
    nodes.append({**nodes[0], "databaseId": 111371488291, "name": name, "conclusion": conclusion})
    github(gh, [pr])
    row = view(repo, "board")["items"][0]
    failed = required or conclusion == "STALE"
    assert row["pr"]["checks"] == ("fail" if failed else "pass")
    assert row["occurrences"] == ([{"id": "check-run:111371488291:2026-10-04T10:00:00Z",
                                    "kind": "checks_failed", "title": f"{name} failed"}] if failed else [])


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
    story(repo, key="WAIT", approved=None)
    repo.git("worktree", "add", str(repo.path.parent / "repo-WAIT"), "story/WAIT")
    waiting = worktree(repo, "story/WAIT")
    # The session checkout has no copy: the consumer must read the story's own worktree.
    assert not (repo.path / "plans/WAIT.md").exists()
    waiting_row = next(r for r in view(repo, "board")["items"] if r["id"] == "WAIT")
    assert waiting_row["approval"] == {"doc": (waiting / "plans/WAIT.md").resolve().as_posix()}
    assert row["approval"] is None
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
    contract(waiting_row, fixture["board"]["items"][1])
    assert view(repo, "board", folder) == view(repo, "board", waiting)
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
        row = next(r for r in view(repo, "board")["items"] if r["id"] == "polish")
        assert row["round"] == 2
        assert row["stages"][0] == {"name": "Build", "status": "pass", "seconds": 10,
                                     "started_at": "2026-10-04T10:00:00Z", "ended_at": "2026-10-04T10:00:10Z"}
        assert row["stages"][1]["status"] == "skipped"
        assert row["stages"][2] == {"name": "Review", "status": "running", "seconds": None,
                                     "started_at": "2026-10-04T10:01:00Z", "ended_at": None}
        assert row["total_seconds"] == 100


@pytest.mark.parametrize("conclusion,required", [(None, None)] + [
    (c, r) for c in ("SKIPPED", "NEUTRAL", "STALE") for r in (True, False)])
def test_3_board_reports_github_occurrences_after_cache_expiry(repo, gh, monkeypatch,
                                                             conclusion, required):
    if conclusion is not None:
        _skipped_checks_fail_only_when_required(repo, gh, conclusion, required)
        return
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


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_4_client_machine_views_follow_the_last_task_merge(env, history):
    # The HTML completion test cannot detect an approved JSON row after a squash merge.
    # Exercise both shipped client lifecycles, including real earlier-release adoption output.
    repo = env.repo
    if history == "new":
        client, remote = env.tmp / "new-client", env.tmp / "new-client.git"
        repo.git("init", "-q", "--bare", "-b", "main", str(remote))
        repo.git("init", "-q", "-b", "main", str(client))
        repo.git("remote", "add", "origin", str(remote), cwd=client)
        env.gh.respond("api", stdout="{}")
        initialized = repo.forge("init", cwd=client)
        assert initialized.returncode == 0, initialized.stderr
        checkout = env.tmp / "new-checkout"
        repo.git("clone", "-q", str(remote), str(checkout))
    else:
        repo.git("switch", "-qc", "fix/upgrade-client")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt Forge v1.2.2")
        env.commit(repo.path, ".factory/fixes/upgrade-client.json", json.dumps({
            "kind": "fix", "branch": "fix/upgrade-client", "why": "Upgrade Forge",
            "done_when": "The client uses this release", "status": "started"}))
        config = repo.path / "forge.toml"
        original = config.read_text("utf-8")
        assert 'version = "v1.2.2"' in original
        assert "## Machine views" not in (repo.path / ".claude/skills/forge/SKILL.md").read_text("utf-8")
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(original.replace('"v1.2.2"', json.dumps(version)), encoding="utf-8")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stderr
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade Forge and sync")
        checkout = env.tmp / "upgraded-checkout"
        remote = repo.git("remote", "get-url", "origin")
        repo.git("clone", "-q", "--branch", "fix/upgrade-client", str(repo.path), str(checkout))
        repo.git("remote", "set-url", "origin", remote, cwd=checkout)
        repo.git("switch", "-qc", "main", cwd=checkout)
        repo.git("push", "-q", "origin", "main", cwd=checkout)
        repo.git("fetch", "-q", "origin", cwd=checkout)
        repo.git("remote", "set-head", "origin", "main", cwd=checkout)
    repo.path = checkout
    for host in (".claude", ".codex"):
        assert "## Machine views" in (checkout / host / "skills/forge/SKILL.md").read_text("utf-8")
    assert 'repo = "client"' in (checkout / "forge.toml").read_text("utf-8")
    # Keep the shipped client files; select the test harness's third-party review configuration.
    version = repo.forge("--version").stdout.split()[-1]
    env.commit(checkout, "forge.toml", f'version = "{version}"\nrepo = "client"\n'
               'workers = "claude"\nmerge = "agent"\nchecks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n')
    repo.git("push", "-q", "origin", "main")
    doc = "\n".join(line for line in STORY_DOC.splitlines() if not line.startswith("| T2 |"))
    item, where = env.start_approved_task(doc)
    row = next(r for r in view(repo, "board")["items"] if r["id"] == "SHOP")
    assert row["stage"] == "approved"
    assert row["children"][0]["next"]["command"] == "forge work SHOP/T1"
    assert view(repo, "next")["next"]["command"] == "forge work SHOP/T1"
    env.open_pr("")
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    # Close leaves saved state waiting for checks; the reviewed-head receipt makes it ready.
    child = next(r for r in view(repo, "board")["items"] if r["id"] == "SHOP")["children"][0]
    assert child["stage"] == "ready"
    assert child["next"]["command"] == "forge merge SHOP/T1"
    fix, fix_tree = env.start_fix(changes={"readme.md": "Welcome.\n"})
    closed = env.close(fix)
    assert closed.returncode == 0, closed.stderr
    row = next(r for r in view(repo, "board")["items"] if r["id"] == fix)
    assert row["stage"] == "ready"
    assert row["next"]["command"] == f"forge merge {fix}"
    # A later commit invalidates that receipt; a machine view must not advertise stale readiness.
    pr = pull(1, f"fix/{fix}")
    pr["headRefOid"] = repo.git("rev-parse", f"fix/{fix}")
    contexts = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]
    contexts["nodes"].append({**contexts["nodes"][0], "name": "tests"})
    github(env.gh, [pr])
    env.commit(fix_tree, "readme.md", "Welcome back.\n")
    row = next(r for r in view(repo, "board")["items"] if r["id"] == fix)
    assert row["stage"] == "waiting for checks"
    assert row["next"]["command"] == f"forge close {fix}"
    assert env.close(fix).returncode == 0
    remote = repo.git("remote", "get-url", "origin")
    gh = env.gh
    gh.respond("api", "graphql", exit=1, stderr="offline")
    state(checkout / ".git/forge/checks-cache.json", fetched_at="2000-01-01T00:00:00+00:00")
    for merged_fix in (False, True):
        if merged_fix:
            # Retain the merged worktree to cover its permission-dependent cleanup instruction.
            repo.git("merge", "--squash", "fix/tidy-readme")
            repo.git("commit", "-qm", "Accept the fix")
            repo.git("push", "-q", "origin", "main")
        repo.git("remote", "set-url", "origin", str(env.tmp / "unreachable.git"))
        offline = {r["id"]: r for r in view(repo, "board")["items"]}
        assert offline["SHOP"]["children"][0]["stage"] == "ready"
        assert offline["SHOP"]["children"][0]["pr"]["checks"] == "unknown"
        assert offline["SHOP"]["children"][0]["next"]["command"] is None
        assert offline[fix]["stage"] == ("merged" if merged_fix else "ready")
        assert offline[fix]["pr"]["checks"] == "unknown"
        assert offline[fix]["next"]["command"] is None
        repo.git("remote", "set-url", "origin", remote)
    github_merge(env, "task/SHOP-T1")
    merged = repo.forge("merge", item)
    assert merged.returncode == 0, merged.stderr
    # Completion is in the merge trailer; the saved story state deliberately remains approved.
    assert json.loads(repo.git("show", "origin/main:.factory/stories/SHOP/story.json"))["status"] == "approved"
    assert "Forge-story-done: " in repo.git("log", "-1", "--format=%B", "origin/main")
    row = next(r for r in view(repo, "board")["items"] if r["id"] == "SHOP")
    assert row["stage"] == "done"
    assert row["children"][0]["stage"] == "merged"
    assert row["next"] == {"command": None, "line": "Shoppers can save a basket is finished."}
    assert "record the outcome" not in view(repo, "next")["next"]["line"]
