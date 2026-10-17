"""Drop and restore fixes through the command, real Git and the GitHub edge.

The lifecycle owns board/next/queue visibility, preservation and team propagation.
Existing fix-start/close tests do not cover dropping. No production seam is used.
"""
import json
import sys

import pytest

from conftest import GH_STUB, Repo, _install
from test_board import seen
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import hold_agents, start, finish
from test_started_branches_claim_the_work import client  # noqa: F401
from test_story import worktree
from test_worker import install_claude, calls

STORY = "FORGE-DROP-1"


def _github(repo, prs=()):
    """GitHub's PR state changes only on its close/reopen API calls."""
    database = repo.bin / "drop-prs.json"
    database.write_text(json.dumps(list(prs)), "utf-8")
    code = '''import json, pathlib, subprocess, sys
from json_log import append_json
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
database = here / "drop-prs.json"
rows = json.loads(database.read_text("utf-8"))
def done(value=""):
    append_json(here / "gh-calls.jsonl", args)
    print(value if isinstance(value, str) else json.dumps(value))
    sys.exit(0)
def save():
    database.write_text(json.dumps(rows), "utf-8")
def pr(key):
    return next((row for row in rows if key in (str(row["number"]), row["headRefName"])), None)
if args[:2] == ["pr", "list"]:
    found = rows
    if "--head" in args:
        found = [row for row in found if row["headRefName"] == args[args.index("--head") + 1]]
    if "--state" in args and args[args.index("--state") + 1] != "all":
        found = [row for row in found if row["state"].lower() == args[args.index("--state") + 1]]
    done(found)
if args[:2] == ["api", "graphql"]:
    nodes = []
    for row in rows:
        if row["state"] != "OPEN":
            continue
        head = subprocess.check_output(["git", "ls-remote", "--heads", "origin",
                                        "refs/heads/" + row["headRefName"]], text=True).split()[0]
        contexts = [{"__typename": "CheckRun", "name": name, "status": "COMPLETED",
                     "conclusion": "SUCCESS"} for name in ("tests", "forge-pr-check")]
        nodes.append({**row, "headRefOid": head, "commits": {"nodes": [{"commit": {
            "oid": head, "statusCheckRollup": {"contexts": {
                "pageInfo": {"hasNextPage": False}, "nodes": contexts}}}}]}})
    done({"data": {"repository": {"pullRequests": {"nodes": nodes}}}})
if args[:2] == ["pr", "create"]:
    branch = args[args.index("--head") + 1]
    rows.append({"number": 7, "headRefName": branch, "state": "OPEN", "baseRefName": "main",
                 "url": "https://github.com/acme/shop/pull/7", "body": "", "isDraft": True})
    save()
    done(rows[-1]["url"])
if args[:2] == ["pr", "view"]:
    row = pr(args[2])
    if row is None:
        sys.exit(1)
    if "--jq" in args:
        done(row["state"])
    head = subprocess.check_output(["git", "rev-parse", "origin/" + row["headRefName"]], text=True).strip()
    done({**row, "headRefOid": head, "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"})
if args[:2] in (["pr", "close"], ["pr", "reopen"], ["pr", "comment"], ["pr", "ready"], ["pr", "edit"]):
    row = pr(args[2])
    if row is None:
        sys.exit(1)
    if args[1] in ("close", "reopen"):
        row["state"] = "CLOSED" if args[1] == "close" else "OPEN"
    if args[1] == "ready":
        row["isDraft"] = "--undo" in args
    if "--comment" in args:
        row.setdefault("comments", []).append(args[args.index("--comment") + 1])
    if args[1] == "comment":
        row.setdefault("comments", []).append(args[args.index("--body") + 1])
    save()
    done()
'''
    fallback = GH_STUB.format(python=sys.executable).split("\n", 1)[1]
    _install(repo.bin, "gh", "#!" + sys.executable + "\n" + code + fallback)
    return database


def _pr(state="OPEN"):
    return {"number": 7, "headRefName": "fix/unwanted", "state": state,
            "title": "Readers see a greeting", "body": "", "isDraft": False,
            "url": "https://github.com/acme/shop/pull/7", "baseRefName": "main"}


def _start(repo, slug="unwanted", cwd=None):
    made = repo.forge("fix", "start", "Readers can see a greeting", "--done",
                      "Readers see the greeting", "--slug", slug, cwd=cwd)
    assert made.returncode == 0, made.stdout + made.stderr
    return worktree(repo, "fix/" + slug)


@pytest.mark.parametrize("pull_request", [False, True], ids=["no-pull-request", "open-pull-request"])
def test_1_drop_hides_a_fix_and_preserves_its_remote_commits(client, pull_request):
    where = _start(client)
    data = _github(client, [_pr()] if pull_request else [])
    (where / "greeting.txt").write_text("Hello readers\n", "utf-8")
    (where / ".gitignore").write_text("node_modules/\n", "utf-8")
    (where / "node_modules").mkdir()
    (where / "node_modules" / "rebuildable.txt").write_text("cache", "utf-8")
    client.git("add", "-A", cwd=where)
    client.git("commit", "-qm", "Greet readers", cwd=where)
    original = client.git("rev-parse", "HEAD", cwd=where)
    default = client.git("rev-parse", "origin/main")
    dropped = client.forge("fix", "drop", "unwanted", "--because", "The greeting is no longer needed")
    assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    assert not where.exists()
    assert client.git("branch", "--list", "fix/unwanted") == ""
    remote = client.git("ls-remote", "origin", "refs/heads/fix/unwanted").split()[0]
    assert client.git("merge-base", "--is-ancestor", original, remote) == ""
    assert client.git("show", remote + ":greeting.txt") == "Hello readers"
    assert client.git("rev-parse", "origin/main") == default
    if pull_request:
        pr = json.loads(data.read_text("utf-8"))[0]
        assert pr["state"] == "CLOSED"
        assert any("The greeting is no longer needed" in comment for comment in pr["comments"])
    else:
        assert json.loads(data.read_text("utf-8")) == []
    board = client.forge("board", "--json")
    assert board.returncode == 0, board.stdout + board.stderr
    assert "unwanted" not in {row["id"] for row in json.loads(board.stdout)["items"]}
    assert "unwanted" not in client.forge("next").stdout
    page = client.forge("board")
    assert page.returncode == 0, page.stdout + page.stderr
    assert "Readers can see a greeting" not in seen(client.path / ".git/forge/board.html")
    queued = client.forge("land", "--all")
    assert queued.returncode == 0, queued.stdout + queued.stderr
    assert "unwanted" not in queued.stdout
    again = client.forge("fix", "start", "Another greeting", "--done", "Another greeting is visible",
                         "--slug", "unwanted")
    assert again.returncode == 0, again.stdout + again.stderr
    assert "fix/unwanted-2" in again.stdout


@pytest.mark.parametrize("kept", [False, True], ids=["recreated-worktree", "kept-local-data"])
def test_2_undo_restores_work_pr_and_close_step(env, kept):
    repo = env.repo
    where = _start(repo)
    data = _github(repo)
    env.commit(where, "greeting.txt", "Hello readers\n", "Greet readers")
    closed = repo.forge("close", "unwanted")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "ready" in closed.stdout.lower()
    before = repo.git("rev-parse", "HEAD", cwd=where)
    if kept:
        env.commit(where, ".gitignore", "local-data/\n", "Keep local data private")
        (where / "local-data").mkdir()
        (where / "local-data" / "customers.txt").write_text("keep this data", "utf-8")
    dropped = repo.forge("fix", "drop", "unwanted", "--because", "Pause the greeting")
    assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    assert where.exists() == kept
    if kept:
        assert "local-data" in dropped.stdout
        hidden = repo.forge("board", "--json")
        assert hidden.returncode == 0, hidden.stdout + hidden.stderr
        assert "unwanted" not in {row["id"] for row in json.loads(hidden.stdout)["items"]}
        assert "unwanted" not in repo.forge("next").stdout
        queued = repo.forge("land", "--all")
        assert queued.returncode == 0, queued.stdout + queued.stderr
        assert "unwanted" not in queued.stdout
        # Someone else can publish an additional commit while the worktree is retained.
        peer = repo.path.parent / "publisher"
        repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(peer))
        repo.git("switch", "-q", "fix/unwanted", cwd=peer)
        (peer / "published.txt").write_text("Published elsewhere\n", "utf-8")
        repo.git("add", "published.txt", cwd=peer)
        repo.git("commit", "-qm", "Publish from another checkout", cwd=peer)
        repo.git("push", "-q", "origin", "fix/unwanted", cwd=peer)
    restored = repo.forge("fix", "drop", "unwanted", "--undo")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    # A teammate has no local close receipt. A legacy PR has no shared time record,
    # and green checks alone cannot make its newly restored commit ready to merge.
    observer = repo.path.parent / "restore-observer"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(observer))
    viewer = Repo(observer, repo.bin)
    observed = viewer.forge("board", "--json")
    assert observed.returncode == 0, observed.stdout + observed.stderr
    row = next(row for row in json.loads(observed.stdout)["items"] if row["id"] == "unwanted")
    assert row["gates"]["ci"]["status"] == "green"
    assert row["stage"] == "waiting for checks"
    assert "ready to merge" not in viewer.forge("next").stdout.lower()
    assert "Next: forge close unwanted" in restored.stdout
    assert worktree(repo, "fix/unwanted").resolve() == where.resolve()
    assert repo.git("merge-base", "--is-ancestor", before, "HEAD", cwd=where) == ""
    assert (where / "greeting.txt").read_text("utf-8") == "Hello readers\n"
    assert json.loads(data.read_text("utf-8"))[0]["state"] == "OPEN"
    if kept:
        assert (where / "local-data/customers.txt").read_text("utf-8") == "keep this data"
        assert (where / "published.txt").read_text("utf-8") == "Published elsewhere\n"
    board = repo.forge("board", "--json")
    assert board.returncode == 0, board.stdout + board.stderr
    assert "unwanted" in {row["id"] for row in json.loads(board.stdout)["items"]}
    assert "Next: forge close unwanted" in repo.forge("next").stdout
    log = install_claude(repo)
    worked = repo.forge("work", "unwanted")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert calls(log), "Restored work must reach the worker"


def test_3_fetch_shows_drop_and_restore_in_a_teammates_checkout(client):
    where = _start(client)
    _github(client, [_pr()])
    peer = client.path.parent / "teammate"
    client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(peer))
    viewer = Repo(peer, client.bin)
    listed = viewer.forge("board", "--json")
    assert listed.returncode == 0, listed.stdout + listed.stderr
    assert "unwanted" in {row["id"] for row in json.loads(listed.stdout)["items"]}
    dropped = client.forge("fix", "drop", "unwanted", "--because", "Pause this work")
    assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    viewer.git("fetch", "-q", "origin")
    listed = viewer.forge("board", "--json")
    assert listed.returncode == 0, listed.stdout + listed.stderr
    assert "unwanted" not in {row["id"] for row in json.loads(listed.stdout)["items"]}
    assert "unwanted" not in viewer.forge("next").stdout
    restored = client.forge("fix", "drop", "unwanted", "--undo")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    viewer.git("fetch", "-q", "origin")
    listed = viewer.forge("board", "--json")
    assert listed.returncode == 0, listed.stdout + listed.stderr
    assert "unwanted" in {row["id"] for row in json.loads(listed.stdout)["items"]}
    assert "unwanted" in viewer.forge("next").stdout
    assert where.exists()


@pytest.mark.parametrize("blocked", ["dirty", "merged", "stacked"])
def test_4_drop_refuses_without_changing_work_or_pull_request(env, blocked):
    repo = env.repo
    where = _start(repo)
    data = _github(repo, [_pr("MERGED" if blocked == "merged" else "OPEN")])
    if blocked == "dirty":
        (where / "uncommitted.txt").write_text("Never lose this\n", "utf-8")
    elif blocked == "stacked":
        _start(repo, "depends-on-greeting", cwd=where)
    before = (repo.git("rev-parse", "HEAD", cwd=where),
              repo.git("ls-remote", "origin", "refs/heads/fix/unwanted"), data.read_bytes(),
              repo.git("status", "--porcelain", cwd=where))
    dropped = repo.forge("fix", "drop", "unwanted", "--because", "Not needed")
    assert dropped.returncode == 1, dropped.stdout + dropped.stderr
    assert "Next:" in dropped.stderr
    assert {"dirty": "uncommitted", "merged": "merged", "stacked": "depends-on-greeting"}[blocked] in dropped.stderr.lower()
    assert where.exists()
    assert before == (repo.git("rev-parse", "HEAD", cwd=where),
                      repo.git("ls-remote", "origin", "refs/heads/fix/unwanted"), data.read_bytes(),
                      repo.git("status", "--porcelain", cwd=where))


def test_5_drop_refuses_while_a_real_forge_run_holds_the_fix(env, tmp_path):
    repo = env.repo
    where = _start(repo)
    data = _github(repo, [_pr()])
    hold_agents(env)
    worker, output = start(repo.path, tmp_path / "working-fix", repo, "work", "unwanted")
    try:
        _until(lambda: (repo.bin / ("started-" + where.name)).exists() or worker.poll() is not None,
               "the fix's worker to start")
        assert worker.poll() is None, output.read_text("utf-8")
        before = (repo.git("rev-parse", "HEAD", cwd=where),
                  repo.git("ls-remote", "origin", "refs/heads/fix/unwanted"), data.read_bytes())
        dropped = repo.forge("fix", "drop", "unwanted", "--because", "Pause this work")
        assert dropped.returncode == 1, dropped.stdout + dropped.stderr
        assert "Next:" in dropped.stderr
        assert "running" in dropped.stderr.lower() or "holds" in dropped.stderr.lower()
        assert where.exists()
        assert before == (repo.git("rev-parse", "HEAD", cwd=where),
                          repo.git("ls-remote", "origin", "refs/heads/fix/unwanted"), data.read_bytes())
    finally:
        finish(repo, [worker])
