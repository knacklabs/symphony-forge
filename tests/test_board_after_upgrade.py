"""An upgrade rebuilds older item histories from real Git and GitHub evidence.

Audit: previous time-history coverage starts with local logs. A squash and
deleted branch leave no such logs, and weekly searches extend past the exact
42-day window. Only uv, GitHub and the reviewer are third-party fakes; no
production seam or prebuilt time record supplies the asserted result.
"""
import json
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone

import pytest

from conftest import GH_STUB, ROOT, _install
from test_board_counts import board, rows
from test_close import GREEN, STORY_DOC, approve_story, env  # noqa: F401
from test_upgrade_command import NAME, RELEASE, unsynced_up  # noqa: F401

STORY = "FORGE-BOARD-2"
NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
UNREACHABLE = ("Couldn't reach GitHub, so older items' time stories weren't rebuilt; "
               "the next forge close on this machine tries again.")

# GitHub persists exactly the body the real command sends it; the edge makes no record.
GITHUB = '''import json, pathlib, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
store = here / "historical-prs.json"
prs = json.loads(store.read_text("utf-8"))
def output(value):
    with open(here / "gh-calls.jsonl", "a", encoding="utf-8") as calls:
        calls.write(json.dumps(args) + "\\n")
    print(json.dumps(value))
    sys.exit(0)
if args[:2] == ["pr", "list"] and "--state" in args:
    if "--head" not in args and (here / "history-unreachable").exists():
        sys.exit("GitHub is unreachable")
    found = prs
    state = args[args.index("--state") + 1].upper()
    if state != "ALL":
        found = [pr for pr in found if pr["state"] == state]
    if "--head" in args:
        found = [pr for pr in found if pr["headRefName"] == args[args.index("--head") + 1]]
    if "--search" in args:
        low, _, high = args[args.index("--search") + 1].removeprefix("merged:").partition("..")
        found = [pr for pr in found if low <= (pr.get("mergedAt") or "")[:10] <= high]
    output(found)
if args[:2] == ["pr", "list"] and "--head" in args:
    found = [pr for pr in prs if pr["headRefName"] == args[args.index("--head") + 1]]
    if found:
        output(found)
if args[:2] == ["pr", "view"]:
    found = next((pr for pr in prs if str(pr["number"]) == args[2] or pr["headRefName"] == args[2]), None)
    if found:
        output(found)
if args[:2] == ["pr", "create"] and args[args.index("--head") + 1] == "task/SHOP-T2":
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    path = args[args.index("--body-file") + 1]
    body = sys.stdin.read() if path == "-" else pathlib.Path(path).read_text("utf-8")
    prs.append({"number": 17, "headRefName": "task/SHOP-T2", "headRefOid": head,
                "baseRefName": "main", "state": "OPEN", "isDraft": False,
                "title": "Show a saved basket", "body": body, "mergedAt": None, "mergedBy": None,
                "author": {"login": "starter", "name": "Original Starter"},
                "url": "https://github.com/acme/shop/pull/17"})
    store.write_text(json.dumps(prs), "utf-8")
    print("https://github.com/acme/shop/pull/17")
    sys.exit(0)
if args[:2] == ["pr", "edit"]:
    found = next((pr for pr in prs if str(pr["number"]) == args[2] or pr["headRefName"] == args[2]), None)
    if found and "--body-file" in args:
        if (here / "history-reject-edit").exists() and found["number"] == 11:
            sys.exit("GitHub refused this body edit")
        path = args[args.index("--body-file") + 1]
        found["body"] = sys.stdin.read() if path == "-" else pathlib.Path(path).read_text("utf-8")
        store.write_text(json.dumps(prs), "utf-8")
        output({})
if args and args[0] == "api" and any("/check-runs" in arg for arg in args):
    endpoint = next(arg for arg in args if "/check-runs" in arg)
    head = endpoint.split("/commits/", 1)[1].split("/", 1)[0]
    checks = json.loads((here / "historical-checks.json").read_text("utf-8"))
    if head in checks:
        runs = checks[head]
        if "--jq" in args:
            with open(here / "gh-calls.jsonl", "a", encoding="utf-8") as calls:
                calls.write(json.dumps(args) + "\\n")
            for run in runs:
                print(json.dumps(run))
            sys.exit(0)
        output([{"check_runs": runs}] if "--slurp" in args else {"check_runs": runs})
'''


class History:
    def __init__(self, up, monkeypatch):
        self.up, self.env, self.repo = up, up.env, up.repo
        self.monkeypatch, self.prs, self.checks = monkeypatch, [], {}
        self.main = self.repo.path
        self.remote = self.repo.git("remote", "get-url", "origin")
        self.at(NOW)
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", self.main, dirs_exist_ok=True)
        old = (self.main / "forge.toml").read_text("utf-8").replace('"v1.2.2"', '"v1.2.11"')
        old = old.replace('workers = "codex"', 'workers = "claude"')
        self.repo.write("forge.toml", old)
        self.repo.git("config", "core.hooksPath", (up.tmp / "no-hooks").as_posix())
        self.repo.git("add", "-A")
        self.repo.git("commit", "-qm", "Client adopted on an earlier release")
        self.repo.git("push", "-q", "origin", "main")

    def story(self):
        self.at(NOW - timedelta(days=30))
        self.repo.git("config", "user.name", "Plan Approver")
        self.repo.git("config", "user.email", "approver@example.test")
        approve_story(self.repo, STORY_DOC)
        self.repo.git("merge", "-q", "--ff-only", "story/SHOP")
        self.repo.git("push", "-q", "origin", "main")

    def at(self, at):
        for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE", "FORGE_NOW"):
            self.monkeypatch.setenv(name, at.isoformat())

    def commit(self, where, path, value, message, at, author="Original Starter"):
        self.at(at)
        self.repo.git("config", "user.name", author)
        self.repo.git("config", "user.email", author.lower().replace(" ", "-") + "@example.test")
        return self.env.commit(where, path, value, message)

    def item(self, name, number, days, merge="squash", task=None, no_pr=False):
        item = "SHOP/" + task if task else name
        branch = "task/SHOP-" + task if task else "fix/" + name
        path = f".factory/stories/SHOP/tasks/{task}.json" if task else f".factory/fixes/{name}.json"
        where = self.up.tmp / ("old-" + name)
        self.repo.git("worktree", "add", "-q", "-b", branch, str(where), "main")
        merged = NOW - timedelta(days=days) if days is not None else None
        begin = (merged or NOW) - timedelta(days=5)
        state = {"kind": "task" if task else "fix", "branch": branch, "status": "working",
                 "why": "Readers see " + name, "done_when": "The text is clear",
                 "base": self.repo.git("rev-parse", "main"),
                 "steps": [{"step": "start", "at": begin.isoformat()}]}
        self.commit(where, path, json.dumps(state), "Start the fix: " + name, begin)
        self.commit(where, name + ".py", "print('first')\n", "Write the greeting", begin + timedelta(hours=1))
        heads = []
        for round_, outcome in enumerate(("blocked", "clean"), 1):
            at = begin + timedelta(days=round_)
            reviewed = self.repo.git("rev-parse", "HEAD", cwd=where)
            findings = ([{"priority": "P1", "title": "Greeting misses the reader", "file": name + ".py",
                          "body": "Gain 3, Work 2, Harm 3\nThe greeting is missing."}] if round_ == 1 else [])
            state.update(status="fixing" if findings else "waiting for checks", round=round_,
                         review={"commit": reviewed, "status": outcome, "findings": findings,
                                 "blocking_level": "P1", "dismissals": []})
            head = self.commit(where, path, json.dumps(state), f"Review of {item}: {outcome}", at,
                               "Historical Reviewer")
            heads.append(head)
            self.checks[head] = [{**run, "started_at": (at + timedelta(minutes=1)).isoformat(),
                                 "completed_at": (at + timedelta(minutes=3)).isoformat()} for run in GREEN]
            self.repo.git("push", "-q", "origin", branch)
            if round_ == 1:
                self.commit(where, name + ".py", "print('hello reader')\n", "Repair the greeting",
                            at + timedelta(hours=1))
        head = heads[-1]
        if not no_pr:
            self.repo.git("push", "-q", "origin", f"{head}:refs/pull/{number}/head")
        if merged:
            self.at(merged)
            if merge == "squash":
                self.repo.git("merge", "-q", "--squash", branch)
                self.repo.git("commit", "-qm", "Readers see " + name)
            else:
                self.repo.git("merge", "-q", "--ff-only" if merge == "ff" else "--no-ff", "--no-edit", branch)
            self.repo.git("push", "-q", "origin", "main")
            self.repo.git("worktree", "remove", str(where))
            self.repo.git("branch", "-D", branch)
            self.repo.git("push", "-q", "origin", "--delete", branch)
        pr = {"number": number, "headRefName": branch, "headRefOid": head,
                        "baseRefName": "main", "state": "MERGED" if merged else "OPEN",
                        "title": "Readers see " + name, "body": "Owner notes remain.\n", "isDraft": False,
                        "mergedAt": merged.isoformat() if merged else None,
                        "mergedBy": {"login": "merger", "name": "Human Merger"} if merged else None,
                        "author": {"login": "starter", "name": "Original Starter"},
                        "url": f"https://github.com/acme/shop/pull/{number}",
                        "statusCheckRollup": [{"name": "tests", "status": "COMPLETED", "conclusion": "SUCCESS"},
                                              {"name": "forge-pr-check", "status": "COMPLETED", "conclusion": "SUCCESS"}]}
        if not no_pr:
            self.prs.append(pr)
        return item, where

    def publish(self):
        (self.repo.bin / "historical-prs.json").write_text(json.dumps(self.prs), "utf-8")
        (self.repo.bin / "historical-checks.json").write_text(json.dumps(self.checks), "utf-8")
        fallback = GH_STUB.format(python=sys.executable).split("\n", 1)[1]
        _install(self.repo.bin, "gh", "#!" + sys.executable + "\n" + GITHUB + fallback)
        self.at(NOW)

    def stored(self):
        return {pr["number"]: pr for pr in json.loads(
            (self.repo.bin / "historical-prs.json").read_text("utf-8"))}

    def record(self, number):
        match = re.search(r"<!-- forge:time-record (\{.*?\}) -->", self.stored()[number]["body"], re.S)
        return json.loads(match[1]) if match else None

    def clear_caches(self):
        for cache in self.up.tmp.rglob("prs-cache.json"):
            cache.unlink()


@pytest.mark.parametrize("failure", [None, "read", "edit"], ids=["reachable", "retry-read", "retry-edit"])
def test_10_upgrade_rebuilds_old_items_and_retries_missing_records_on_close(unsynced_up, monkeypatch, failure):
    history = History(unsynced_up, monkeypatch)
    up, repo = history.up, history.repo
    history.story()
    history.item("saved-basket", 10, 24, task="T1")
    history.item("deleted", 11, 21)
    history.item("ordinary-merge", 12, 14, merge="merge")
    history.item("fast-forward", 13, 14, merge="ff")
    history.item("inside-cut", 14, 41)
    history.item("exact-cut", 18, 42)
    history.item("outside-cut", 15, 43)
    opened, _ = history.item("ready-before-upgrade", 16, None)
    history.item("open-part", 17, None, task="T2", no_pr=True)
    history.publish()
    marker = history.main / ".git/forge/backfill-pending"
    failing = repo.bin / ("history-unreachable" if failure == "read" else "history-reject-edit")
    if failure:
        failing.touch()
    upgraded = up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    if failure:
        assert UNREACHABLE in upgraded.stdout + upgraded.stderr
        assert marker.is_file()
        failing.unlink()
        # A different fix started from the upgraded checkout provides the next
        # close, without depending on an upgrade rerun remaining available.
        repo.path = up.folder
        retry_item, retry_where = up.env.start(
            "retry-history", "fix/retry-history", ".factory/fixes/retry-history.json",
            {"kind": "fix", "why": "Readers see a heading", "done_when": "The heading is clear",
             "base": repo.git("rev-parse", "HEAD")}, {"heading.txt": "Welcome readers\n"})
        repo.path = history.main
        retried = repo.forge("close", retry_item, cwd=retry_where)
        assert retried.returncode == 0, retried.stdout + retried.stderr
    assert history.record(11), "Upgrade must write the deleted branch's original history into its PR"
    assert not marker.exists()
    for number in (10, 11, 12, 13, 14, 16, 18):
        record = history.record(number)
        assert record and record["rebuilt"] is True
        assert "Owner notes remain." in history.stored()[number]["body"]
        assert len([e for e in record["events"] if e["event"] == "review result"]) == 2
    assert history.record(15) is None, "The exact 42-day cut excludes a merge 43 days ago"
    assert 17 not in history.stored(), "An open part without a PR has no upgrade-time record store"
    before = history.stored()
    def historical_checks():
        return [call for call in up.env.gh.calls() if any(
            "/commits/" + head + "/check-runs" in arg for head in history.checks for arg in call)]

    checks = historical_checks()
    again = up.run(RELEASE)
    assert again.returncode == 0, again.stdout + again.stderr
    assert history.stored() == before, "A repeated upgrade must not rewrite an existing record"
    assert historical_checks() == checks

    history.clear_caches()
    before_board = repo.git("rev-parse", "HEAD")
    data = board(repo)
    visible = rows(data)
    for item in ("SHOP/T1", "deleted", "ordinary-merge", "fast-forward", "inside-cut", "exact-cut"):
        row = visible[item]
        branch = "task/SHOP-T1" if item == "SHOP/T1" else "fix/" + item
        pr = next(pr for pr in before.values() if pr["headRefName"] == branch)
        assert row["started_by"] == "Original Starter"
        assert row["merged_by"]["name"] == "Human Merger"
        assert row["merged_at"] == pr["mergedAt"]
        assert row["gates"]["review"]["status"] == "clean"
        assert row["rebuilt"] is True
        assert row["working_seconds"] == 0
        assert row["unknown_seconds"] > 0
        assert row["time_breakdown"]["building"] is None
        assert row["time_breakdown"]["reviewing"] is None
        assert [(r["new_findings"], r["repeat_findings"]) for r in row["rounds"]] == [(1, 0), (0, 0)]
        assert row["time_breakdown"]["waiting_for_ci"] == 240
        assert row["time_breakdown"]["waiting_for_owner"] > 0
    assert visible["SHOP/T1"]["approved_by"] == "Plan Approver"
    assert not visible["outside-cut"].get("rebuilt")
    assert visible["outside-cut"]["time_breakdown"]["building"] is None
    assert sum(week["parts"] for week in data["team"]["pace"]["weeks"]) == 1
    assert sum(week["fixes"] for week in data["team"]["pace"]["weeks"]) >= 5
    assert any(row["id"] == opened and row["reason"] == "merge" for row in data["team"]["needs_you"])
    page = up.tmp / "rebuilt-board.html"
    written = repo.forge("board", "--out", page.as_posix())
    assert written.returncode == 0, written.stdout + written.stderr
    assert "rebuilt from history" in page.read_text("utf-8").lower()
    assert repo.git("rev-parse", "HEAD") == before_board, "Reading the board must add no commit"

    # The second machine never upgraded and has neither old receipts nor local
    # logs. The shared clean review still makes the open fix ready immediately.
    clone = up.tmp / "second-machine"
    repo.git("clone", "-q", history.remote, clone.as_posix())
    repo.path = clone
    fresh = rows(board(repo))[opened]
    assert fresh["stage"] == "ready"
    assert not (clone / ".git/forge/events.jsonl").exists()
    assert not (clone / ".git/forge/timings.jsonl").exists()
    assert not (clone / ".git/forge/ready" / (opened + ".json")).exists()
    next_ = repo.forge("next")
    assert next_.returncode == 0, next_.stdout + next_.stderr
    assert "ready-before-upgrade" in next_.stdout and "merge" in next_.stdout.lower()

    # Land the actual upgrade in GitHub's disposable origin so a second clone's
    # first close uses the installed release, just as after a human merges it.
    landed = up.tmp / "github-upgrade"
    repo.git("clone", "-q", history.remote, landed.as_posix())
    repo.git("merge", "-q", "--ff-only", "origin/fix/" + NAME, cwd=landed)
    repo.git("push", "-q", "origin", "main", cwd=landed)
    repo.git("fetch", "-q", "origin")
    repo.git("merge", "-q", "--ff-only", "origin/main")
    for item, branch, number in ((opened, "fix/" + opened, 16), ("SHOP/T2", "task/SHOP-T2", 17)):
        resumed = up.tmp / ("second-" + branch.replace("/", "-"))
        repo.git("worktree", "add", "-q", "-b", branch, resumed.as_posix(), "origin/" + branch)
        closed = repo.forge("close", item, cwd=resumed)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        record = history.record(number)
        assert record and record["rebuilt"] is True
        older = [e for e in record["events"] if e["event"] == "review result"
                 and e["at"] < NOW.isoformat()]
        assert len(older) == 2, "First publication must recover the older committed rounds on this machine"
