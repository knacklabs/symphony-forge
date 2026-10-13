"""Stories, parts and fixes each have one state and one count, the same on every machine.

Real Forge commands and git build every item; only GitHub, the reviewer and the reader are
stubs. Board and next output is all the tests read.
"""
import json
import os
import re
import shlex
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import conftest
from test_close import STORY_DOC, approve_story, blocked, body, env, finding  # noqa: F401
from test_board_github_once import github_read_once
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_story import READER, worktree

STORY = "FORGE-BOARD-2"

PLAN = STORY_DOC.replace(
    "| T2 | Show a saved basket | A saved basket shows again after sign-in | 2 | `show.py` | `tests/test_show.py` | T1 | yes |",
    "| T2 | Show a saved basket | A saved basket shows again after sign-in | 2 | `show.py` | `tests/test_show.py` | — | no |\n"
    "| T3 | Share a basket | A shopper can share a basket | 2 | `share.py` | `tests/test_share.py` | — | no |\n"
    "| T4 | Empty a basket | A shopper can empty a basket | 2 | `empty.py` | `tests/test_empty.py` | — | no |")
ONE_PART = STORY_DOC.replace(
    "| T2 | Show a saved basket | A saved basket shows again after sign-in | 2 | `show.py` | `tests/test_show.py` | T1 | yes |\n",
    "")


def clock(monkeypatch, at):
    monkeypatch.setenv("FORGE_NOW", at.isoformat())


def board(repo):
    shown = repo.forge("board", "--json")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    return json.loads(shown.stdout)


def rows(data):
    return {row["id"]: row for parent in data["items"] for row in [parent, *parent["children"]]}


def read_story(repo, key, doc):
    """A story whose plan passed its cold read but is not approved."""
    made = repo.forge("story", "new", key, "A story read but not approved")
    assert made.returncode == 0, made.stdout + made.stderr
    where = worktree(repo, f"story/{key}")
    (where / "plans" / f"{key}.md").write_text(doc, "utf-8")
    read = repo.forge("read", key)
    assert read.returncode == 0, read.stdout + read.stderr
    return where


def github(env, prs):
    """GitHub answers each list with only the rows in the requested state, head and merge dates."""
    gh = env.repo.bin / "gh"
    source = gh.read_text("utf-8")
    if "STATE FILTER" not in source:
        gh.write_text(source.replace('sys.stdout.write(rule["stdout"])', '''output = rule["stdout"]  # STATE FILTER
        if args[:2] == ["pr", "list"] and "--state" in args and output.startswith("[") and args[args.index("--state") + 1] != "all":
            state = args[args.index("--state") + 1].upper()
            output = json.dumps([pr for pr in json.loads(output) if pr.get("state") == state])
        if args[:2] == ["pr", "list"] and "--head" in args and output.startswith("["):
            head = args[args.index("--head") + 1]
            output = json.dumps([pr for pr in json.loads(output) if pr.get("headRefName") == head])
        if args[:2] == ["pr", "list"] and "--search" in args and output.startswith("["):
            query = args[args.index("--search") + 1].removeprefix("merged:")
            low, _, high = query.partition("..")
            output = json.dumps([pr for pr in json.loads(output) if (day := (pr.get("mergedAt") or "")[:10])
                                 and low <= day <= high])
        sys.stdout.write(output)'''), "utf-8")
    env.gh.respond("pr", "list", stdout=json.dumps(prs))


def ready_pr(env, item, branch, number=8):
    calls = env.gh_calls("pr", "edit") or env.gh_calls("pr", "create")
    return {"number": number, "headRefName": branch, "state": "OPEN", "title": "Show a saved basket",
            "body": body(calls[-1]), "isDraft": False, "mergedAt": None, "mergedBy": None,
            "author": {"login": "forge-test", "name": "Forge Test"},
            "headRefOid": env.repo.git("ls-remote", "origin", f"refs/heads/{branch}").split()[0],
            "url": f"https://github.com/acme/shop/pull/{number}"}


def configure(env, merge):
    env.repo.git("merge", "-q", "--ff-only", "origin/main")
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(env.repo.path, "forge.toml", f'version = "{version}"\nstage = "live"\nworkers = "claude"\n'
               f'merge = "{merge}"\ntest = "echo passed"\nchecks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n'
               'models.grill.claude = { model = "opus", effort = "high" }\n')
    env.repo.git("push", "-q", "origin", "main")


def expected(previous, *, ready=1, progress=1):
    return {"stories": {"done": 1, "building": 1, "approved, not started": 1,
                        "waiting for approval": 1, "planning": 2, "no plan yet": 1},
            "parts": {"done": 1, "ready to merge": ready, "in progress": progress, "to do": 2},
            "fixes": {"done": 1 + previous, "ready to merge": 1, "in progress": 1, "to do": 0},
            "finished_last_7_days": {"parts": 1, "fixes": 1 + previous}}


@pytest.mark.parametrize("case", ["counts", "newer-push", "github-once", "approved-not-started", "newer-findings",
                                  "older-part"])
@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_every_item_has_one_state_and_the_same_counts_on_every_machine(env, monkeypatch, previous, case):
    if case == "github-once":
        github_read_once(env, monkeypatch, previous)
        return
    if case == "older-part":
        older_part(env, monkeypatch, previous)
        return
    if case == "newer-push":
        newer_push(env, monkeypatch, previous)
        return
    if case == "newer-findings":
        newer_findings(env, monkeypatch, previous)
        return
    if case == "approved-not-started":
        approved_not_started(env, previous)
        return
    client(env, previous)
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    configure(env, "agent")
    now = datetime.now(timezone.utc)
    clock(monkeypatch, now)

    # One story per state: done, building, approved but not started, waiting for approval,
    # planning (twice: a draft, and a plan edited above For the builders after its read) and no plan.
    approve_story(env.repo, PLAN)
    env.repo.git("merge", "-q", "--no-edit", "story/SHOP")
    env.repo.git("push", "-q", "origin", "main")
    approve_story(env.repo, ONE_PART, key="CART")
    read_story(env.repo, "WAIT", ONE_PART)
    edited = read_story(env.repo, "EDIT", ONE_PART)
    env.commit(edited, "plans/EDIT.md", ONE_PART.replace("come back to it", "come back to it later"))
    made = env.repo.forge("story", "new", "DRAFT", "A draft story")
    assert made.returncode == 0, made.stdout + made.stderr
    roadmap = env.repo.path / "plans/roadmap.json"
    items = json.loads(roadmap.read_text("utf-8"))["items"]
    env.commit(env.repo.path, "plans/roadmap.json", json.dumps({"items": items + [
        {"key": key} for key in ("WAIT", "EDIT", "DRAFT") if key not in {i["key"] for i in items}] + [
        {"key": "IDEA", "title": "An idea with no plan"},
        {"key": "OLD", "title": "A finished story", "status": "done"}]}))
    env.repo.git("push", "-q", "origin", "main")

    # One part per state: T1 merged, T2 ready, T3 in progress, T4 to do; CART's part is to do too.
    folders = {}
    for task in ("T1", "T2", "T3"):
        started = env.repo.forge("task", "start", f"SHOP/{task}")
        assert started.returncode == 0, started.stdout + started.stderr
        folders[task] = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
        env.commit(folders[task], f"{task.lower()}.py", f"print('{task}')\n")
    env.repo.git("merge", "-q", "--no-edit", "task/SHOP-T1")
    env.repo.git("push", "-q", "origin", "main", "task/SHOP-T1")
    closed = env.close("SHOP/T2")
    assert closed.returncode == 0, closed.stdout + closed.stderr

    # An open fix, and a fix merged on GitHub whose local state still says working.
    opened = env.repo.forge("fix", "start", "Keep the basket", "--done", "The basket stays", "--slug", "keep")
    assert opened.returncode == 0, opened.stdout + opened.stderr
    env.start("gone", "fix/gone", ".factory/fixes/gone.json",
              {"kind": "fix", "why": "Tidy the readme", "done_when": "It is tidy"}, {"gone.py": "x = 1\n"})
    env.repo.git("push", "-q", "origin", "fix/gone")
    pr = ready_pr(env, "SHOP/T2", "task/SHOP-T2")
    # A fix closed ready here too.
    shelf = env.repo.forge("fix", "start", "Shelve a basket", "--done", "A basket can wait", "--slug", "shelf")
    assert shelf.returncode == 0, shelf.stdout + shelf.stderr
    env.commit(worktree(env.repo, "fix/shelf"), "shelf.py", "print('shelf')\n")
    closed = env.close("shelf")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    shelf_pr = ready_pr(env, "shelf", "fix/shelf", number=10)
    merged = {"number": 9, "headRefName": "fix/gone", "state": "MERGED", "title": "Tidy the readme",
              "body": "", "isDraft": False, "mergedAt": now.isoformat(), "url": "https://github.com/acme/shop/pull/9",
              "mergedBy": {"login": "ana", "name": "Ana"}, "author": {"login": "ana", "name": "Ana"},
              "headRefOid": env.repo.git("rev-parse", "fix/gone")}
    github(env, [pr, shelf_pr, merged])
    clock(monkeypatch, now := now + timedelta(minutes=2))

    machine_a = env.repo.path
    data = board(env.repo)
    assert data["team"]["counts"] == expected(previous)
    # The page's totals line prints the same counts, finished ones included.
    page = env.tmp / "counts-board.html"
    written = env.repo.forge("board", "--out", str(page))
    assert written.returncode == 0, written.stderr
    text = " ".join(re.sub(r"<[^>]+>", " ", page.read_text("utf-8")).split())
    for line in ("Stories — Done: 1; Building: 1; Approved, not started: 1; Waiting for approval: 1; "
                 "Planning: 2; No plan yet: 1",
                 "Parts — Done: 1; Ready to merge: 1; In progress: 1; To do: 2",
                 f"Fixes — Done: {1 + previous}; Ready to merge: 1; In progress: 1; To do: 0",
                 f"Finished in the last 7 days — Parts: 1; Fixes: {1 + previous}"):
        assert line in text, (line, text[:800])
    assert set(data["team"]) >= {"sentence", "counts", "needs_you", "in_progress", "blocked", "pace",
                                 "go_live", "trends", "around_forge"}
    assert "stage_counts" not in data and "kind_stage_counts" not in data
    states = {key: row["state"] for key, row in rows(data).items()}
    assert {k: states[k] for k in ("SHOP", "CART", "WAIT", "EDIT", "DRAFT", "IDEA")} == {
        "SHOP": "building", "CART": "approved, not started", "WAIT": "waiting for approval",
        "EDIT": "planning", "DRAFT": "planning", "IDEA": "no plan yet"}
    assert states["SHOP/T2"] == "ready to merge" and states["SHOP/T3"] == "in progress"
    assert states["gone"] == "done" and states["keep"] == "in progress"
    following = env.repo.forge("next")
    assert "SHOP/T2 is ready to merge" in following.stdout, following.stdout

    # Machine B has no receipt and no worktree; the pull request's record says T2 is ready.
    # It sees the plan reads once A shares their story branches.
    env.repo.git("push", "-q", "origin", "story/WAIT", "story/EDIT")
    remote = env.repo.git("remote", "get-url", "origin")
    machine_b = env.tmp / "machine-b"
    env.repo.git("clone", "-q", remote, str(machine_b))
    env.repo.path = machine_b
    data = board(env.repo)
    assert data["team"]["counts"] == expected(previous)
    part = rows(data)["SHOP/T2"]
    assert part["state"] == "ready to merge"
    assert part["next"] == {"command": None,
                            "line": "Show a saved basket is ready to merge; Forge Test merges it from their machine."}
    following = env.repo.forge("next")
    assert "SHOP/T2 is ready to merge; Forge Test merges it from their machine." in following.stdout, following.stdout
    assert "forge task start SHOP/T2" not in following.stdout
    assert "The fix shelf is ready to merge; Forge Test merges it from their machine." in following.stdout
    # A part and a fix started on A with no pull request yet are started here too, never offered.
    assert env.repo.git("ls-remote", "origin", "refs/heads/task/SHOP-T3", "refs/heads/fix/keep").count("\n") == 1
    assert "forge task start SHOP/T3" not in following.stdout
    assert "SHOP/T3 was started by Forge Test and runs on their machine." in following.stdout
    assert "The fix keep was started by Forge Test and runs on their machine." in following.stdout
    assert "forge work SHOP/T3" not in following.stdout and "forge work keep" not in following.stdout
    there = rows(json.loads(env.repo.forge("next", "--json").stdout))
    assert there["SHOP/T3"]["next"]["command"] is None and there["keep"]["next"]["command"] is None

    # In a human-merge repo the same part gives the human-merge line.
    env.repo.path = machine_a
    configure(env, "human")
    clock(monkeypatch, now := now + timedelta(minutes=2))
    env.repo.path = machine_b
    part = rows(board(env.repo))["SHOP/T2"]
    assert part["next"]["line"] == f"Show a saved basket is ready to merge: {pr['url']}"

    # Machine A without its receipt closes again to write one.
    env.repo.path = machine_a
    (machine_a / ".git/forge/ready/SHOP/T2.json").unlink()
    machine = env.repo.forge("next", "--json")
    assert rows(json.loads(machine.stdout))["SHOP/T2"]["next"]["command"] == "forge close SHOP/T2"
    again = env.close("SHOP/T2")
    assert again.returncode == 0, again.stdout + again.stderr
    assert (machine_a / ".git/forge/ready/SHOP/T2.json").is_file()
    assert rows(board(env.repo))["SHOP/T2"]["state"] == "ready to merge"


def newer_push(env, monkeypatch, previous):
    """A newer push ends readiness on every machine; a clean close of it brings readiness back,
    and a worktree behind a newer ready head is brought up to date and closed before merging."""
    client(env, previous)
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    configure(env, "agent")
    now = datetime.now(timezone.utc)
    clock(monkeypatch, now)
    approve_story(env.repo, PLAN)
    env.repo.git("merge", "-q", "--no-edit", "story/SHOP")
    env.repo.git("push", "-q", "origin", "main")
    started = env.repo.forge("task", "start", "SHOP/T2")
    assert started.returncode == 0, started.stdout + started.stderr
    folder = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    env.commit(folder, "t2.py", "print('T2')\n")
    closed = env.close("SHOP/T2")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    github(env, [ready_pr(env, "SHOP/T2", "task/SHOP-T2")])
    machine_a = env.repo.path
    remote = env.repo.git("remote", "get-url", "origin")
    machine_b = env.tmp / "machine-b"
    env.repo.git("clone", "-q", remote, str(machine_b))

    # A third clone pushes another commit: both machines see the part back in progress.
    third = env.tmp / "machine-c"
    env.repo.git("clone", "-q", "-b", "task/SHOP-T2", remote, str(third))
    env.commit(third, "t2.py", "print('newer')\n")
    env.repo.git("push", "-q", "origin", "task/SHOP-T2", cwd=third)
    github(env, [ready_pr(env, "SHOP/T2", "task/SHOP-T2")])  # GitHub reports the new head
    clock(monkeypatch, now := now + timedelta(minutes=2))
    for where in (machine_a, machine_b):
        env.repo.path = where
        data, machine = board(env.repo), env.repo.forge("next", "--json")
        assert rows(data)["SHOP/T2"]["state"] == "in progress", where
        assert rows(json.loads(machine.stdout))["SHOP/T2"]["state"] == "in progress", where

    # A closes the newer commit clean; after a fetch both machines see it ready again.
    env.repo.path = machine_a
    env.repo.git("merge", "-q", "--ff-only", "origin/task/SHOP-T2", cwd=folder)
    closed = env.close("SHOP/T2")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    github(env, [ready_pr(env, "SHOP/T2", "task/SHOP-T2")])
    clock(monkeypatch, now := now + timedelta(minutes=2))
    for where in (machine_a, machine_b):
        env.repo.path = where
        assert rows(board(env.repo))["SHOP/T2"]["state"] == "ready to merge", where

    # B pushes and closes a newer commit: A's worktree is behind it, so A brings it up to date
    # and closes before merging, since forge merge needs A's own receipt.
    env.repo.path = machine_b
    resumed = env.tmp / "machine-b-T2"
    env.repo.git("fetch", "-q", "origin")
    env.repo.git("worktree", "add", "-q", "-b", "task/SHOP-T2", str(resumed), "origin/task/SHOP-T2")
    env.commit(resumed, "t2.py", "print('newest')\n")
    closed = env.close("SHOP/T2")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    github(env, [ready_pr(env, "SHOP/T2", "task/SHOP-T2")])
    clock(monkeypatch, now := now + timedelta(minutes=2))
    env.repo.path = machine_a
    part = rows(board(env.repo))["SHOP/T2"]
    assert part["state"] == "ready to merge"
    assert part["next"] == {"command": None, "line": (
        "Show a saved basket is ready to merge, but this worktree is behind its pull request.")}
    folder_arg = f'"{folder}"' if os.name == "nt" else shlex.quote(str(folder))
    assert f"Next: git -C {folder_arg} pull, then forge close SHOP/T2" in env.repo.forge("next").stdout


def approved_not_started(env, previous):
    """Item 12's first rule: an approved story with no part started is not building, and a fix
    merged on GitHub is done."""
    client(env, previous)
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    configure(env, "human")
    approve_story(env.repo, ONE_PART, key="CART")
    env.start("gone", "fix/gone", ".factory/fixes/gone.json",
              {"kind": "fix", "why": "Tidy the readme", "done_when": "It is tidy"}, {"gone.py": "x = 1\n"})
    env.repo.git("push", "-q", "origin", "fix/gone")
    github(env, [{"number": 9, "headRefName": "fix/gone", "state": "MERGED", "title": "Tidy the readme",
                  "body": "", "isDraft": False, "mergedAt": datetime.now(timezone.utc).isoformat(),
                  "url": "https://github.com/acme/shop/pull/9", "mergedBy": None, "author": None,
                  "headRefOid": env.repo.git("rev-parse", "fix/gone")}])
    data = board(env.repo)
    assert rows(data)["CART"]["state"] == "approved, not started"
    assert data["team"]["counts"]["stories"]["approved, not started"] == 1
    assert data["team"]["counts"]["stories"]["building"] == 0
    assert rows(data)["gone"]["state"] == "done"
    assert data["team"]["counts"]["fixes"]["in progress"] == 0
    page = env.tmp / "board.html"
    written = env.repo.forge("board", "--out", str(page))
    assert written.returncode == 0, written.stderr
    text = re.sub(r"<[^>]+>", " ", page.read_text("utf-8"))
    assert "Approved, not started: 1" in text and "Building: 0" in text

    # An edit to the Why after the read stops it counting as approved, as forge next's gate says.
    plan = worktree(env.repo, "story/CART") / "plans/CART.md"
    env.commit(plan.parent.parent, "plans/CART.md",
               plan.read_text("utf-8").replace("leave.", "leave the shop."))
    assert rows(board(env.repo))["CART"]["state"] == "planning"
    # An edit to what the approval binds needs a new approval too.
    env.commit(plan.parent.parent, "plans/CART.md",
               plan.read_text("utf-8").replace("come back to it", "come back to it later"))
    assert rows(board(env.repo))["CART"]["state"] == "planning"


def newer_findings(env, monkeypatch, previous):
    """Board and next read an item's findings and round at the pull request's head, so an older
    worktree here shows what the newer review on another machine found."""
    client(env, previous)
    configure(env, "human")
    item, _ = env.start_fix(round=1)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    github(env, [ready_pr(env, item, f"fix/{item}")])
    machine_a = env.repo.path
    machine_b = env.tmp / "findings-machine-b"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(machine_b))
    env.repo.path = machine_b
    resumed = env.tmp / "findings-worktree-b"
    env.repo.git("worktree", "add", "-q", "-b", f"fix/{item}", str(resumed), f"origin/fix/{item}")
    env.commit(resumed, "app.py", "print('newer')\n")
    record = resumed / ".factory/fixes" / f"{item}.json"  # a second worker round, as forge work starts it
    env.commit(resumed, record.relative_to(resumed).as_posix(),
               json.dumps({**json.loads(record.read_text("utf-8")), "round": 2, "status": "working"}))
    env.reviews(blocked(finding("P1", "Basket disappears")))
    stopped = env.close(item)
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    newer = json.loads(env.repo.git("show", f"origin/fix/{item}:.factory/fixes/{item}.json"))
    github(env, [ready_pr(env, item, f"fix/{item}")])
    clock(monkeypatch, datetime.now(timezone.utc) + timedelta(minutes=2))

    env.repo.path = machine_a
    local = json.loads(env.repo.git("show", f"fix/{item}:.factory/fixes/{item}.json"))
    assert local["round"] != newer["round"] and not local["review"]["findings"]
    # forge next runs first, before any board fetch, and reads the newer head all the same.
    following = env.repo.forge("next")
    assert "Basket disappears" in following.stdout, following.stdout
    row = rows(board(env.repo))[item]
    assert row["findings"]["titles"] == ["Basket disappears"]
    assert row["round"] == newer["round"]
    assert row["gates"]["review"]["status"] == "blocked"


def older_part(env, monkeypatch, previous):
    """A part of an unfinished story merged before the weekly searches still brings its time from
    its pull request, from one request for everything merged before the weekly searches."""
    client(env, previous)
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    configure(env, "agent")
    then = datetime.now(timezone.utc) - timedelta(weeks=8)
    for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.setenv(name, then.isoformat())
    approve_story(env.repo, PLAN)
    env.repo.git("merge", "-q", "--no-edit", "story/SHOP")
    env.repo.git("push", "-q", "origin", "main")
    started = env.repo.forge("task", "start", "SHOP/T1")
    assert started.returncode == 0, started.stdout + started.stderr
    env.commit(Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1]), "t1.py", "print('T1')\n")
    at = lambda hours: (then - timedelta(hours=hours)).isoformat()  # noqa: E731
    with (env.repo.path / ".git/forge/events.jsonl").open("a", encoding="utf-8") as events:
        for event in ({"id": "T1-phase", "event": "work phase", "phase": "building", "at": at(2)},
                      {"id": "T1-start", "event": "run start", "kind": "worker", "round": 1, "at": at(2)},
                      {"id": "T1-end", "event": "run end", "kind": "worker", "run_id": "T1-start", "at": at(1)}):
            events.write(json.dumps({**event, "item": "SHOP/T1"}) + "\n")
    closed = env.close("SHOP/T1")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    pr = {**ready_pr(env, "SHOP/T1", "task/SHOP-T1"), "state": "MERGED", "mergedAt": then.isoformat()}
    env.repo.git("merge", "-q", "--no-edit", "task/SHOP-T1")
    env.repo.git("push", "-q", "origin", "main")
    github(env, [pr])
    for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.delenv(name)
    clock(monkeypatch, datetime.now(timezone.utc))
    for log in ("events.jsonl", "timings.jsonl"):  # only the pull request remembers the part's time
        (env.repo.path / ".git/forge" / log).unlink(missing_ok=True)
    asked = lambda: [call for call in env.gh_calls("pr", "list")  # noqa: E731
                     if any(arg.startswith("merged:*..") for arg in call)]
    shop = rows(board(env.repo))["SHOP"]
    assert shop["state"] == "building" and "SHOP/T1" not in [c["id"] for c in shop["children"]]
    board(env.repo)
    assert len(asked()) == 1, "asked once a minute"
    # Without the record in its pull request, the part's recorded time is gone from the runway.
    github(env, [{**pr, "body": ""}])
    clock(monkeypatch, datetime.now(timezone.utc) + timedelta(minutes=2))
    bare = rows(board(env.repo))["SHOP"]
    first = lambda row: min(datetime.fromisoformat(i["start"]) for i in row["intervals"])  # noqa: E731
    assert first(shop) <= then - timedelta(hours=2) < first(bare), (shop["intervals"], bare["intervals"])
