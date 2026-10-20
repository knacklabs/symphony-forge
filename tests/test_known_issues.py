"""The board exposes kept review problems from default-branch and original PR evidence.

Exercises src/forge/known_issues.py through the real board command.

Audit: the command's public JSON owns this contract. Losing the persisted list,
reading a squash instead of the PR head, or treating a dismissal as a keep all
change the asserted result. Existing board tests cover counts, not this list.
Only GitHub and the upgrade installer/reviewer are third-party fakes; real Git
retains the historical reviews, and no production seam supplies board results.
"""
import json
import shutil
import sys
from datetime import timedelta

import pytest

from conftest import GH_STUB, ROOT, _install
from test_board_after_upgrade import GITHUB, NOW
from test_board_counts import board
from test_close import env  # noqa: F401
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FORGE-BOARD-3"


@pytest.fixture(params=[False, True], ids=["new-client", "earlier-adoption"])
def kept_history(unsynced_up, monkeypatch, request):
    previous = request.param
    up, env = unsynced_up, unsynced_up.env
    repo = env.repo
    repo.git("config", "core.hooksPath", (up.tmp / "no-hooks").as_posix())
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        env.commit(repo.path, "forge.toml", (repo.path / "forge.toml").read_text("utf-8").replace(
            'workers = "codex"', 'workers = "claude"'), "Adopt an earlier Forge release")
    # This item predates the six-week board runway. Its original reviews only
    # survive in GitHub's pull ref after squash merge and branch deletion.
    at = NOW - timedelta(days=90)
    for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.setenv(name, at.isoformat())
    base = repo.git("rev-parse", "HEAD")
    item, branch = "old-greeting", "fix/old-greeting"
    path = ".factory/fixes/old-greeting.json"
    where = up.tmp / "old-greeting"
    repo.git("worktree", "add", "-q", "-b", branch, where.as_posix(), "main")
    state = {"kind": "fix", "branch": branch, "base": base, "status": "working",
             "why": "Readers see a greeting", "done_when": "The greeting is clear",
             "steps": [{"step": "start", "at": at.isoformat()}]}
    env.commit(where, path, json.dumps(state), "Start the greeting")
    reviewed = env.commit(where, "greeting.py", "print('hello')\n", "Write the greeting")
    findings = [
        {"priority": "P2", "title": "Explain short greetings", "file": "greeting.py", "line": 1,
         "gain": 3, "work": 4, "harm": 2,
         "body": "Gain 3, Work 4, Harm 2\nA longer explanation can follow later."},
        {"priority": "P2", "title": "Older greeting has no example", "file": "greeting.py", "line": 2,
         "body": "An example would help readers."},
        {"priority": "P2", "title": "Dismissed greeting complaint", "file": "greeting.py", "line": 3,
         "body": "The reviewer mistook a deliberate greeting for a defect."}]
    state["review"] = {"commit": reviewed, "status": "clean", "blocking_level": "P1",
                       "findings": findings, "dismissals": [
                           {"finding": 3, "because": "The greeting already meets the requirement"}]}
    env.commit(where, path, json.dumps(state), f"Review of {item}: clean")
    reviewed = env.commit(where, "greeting.py", "print('hello reader')\n", "Clarify the greeting")
    state.update(status="ready", review={"commit": reviewed, "status": "clean",
                                         "blocking_level": "P1", "findings": [], "dismissals": []})
    head = env.commit(where, path, json.dumps(state), f"Review of {item}: clean")
    repo.git("push", "-q", "origin", head + ":refs/pull/11/head")
    repo.git("merge", "-q", "--squash", branch)
    repo.git("commit", "-qm", "Readers see a greeting")
    repo.git("worktree", "remove", where.as_posix())
    repo.git("branch", "-D", branch)
    # A current persisted list is authoritative even when no review survives.
    # An unmerged worktree must not leak its different list into board JSON.
    known = [
        {"file": "reader.py", "line": 7, "title": "Add another example", "gain": 3,
         "work": 3, "harm": 2, "outcome": "follow-up", "reason": "Add it in the next help change"},
        {"file": "reader.py", "line": 9, "title": "Keep the short wording", "gain": 2,
         "work": 2, "harm": 1, "outcome": "lived with", "reason": "The current wording is sufficient"},
        {"file": "reader.py", "line": 12, "title": "An ordinary dismissal", "gain": 2,
         "work": 2, "harm": 1, "outcome": "accepted", "reason": "The report was incorrect"}]
    saved = {**state, "branch": "fix/current-help", "known": known}
    env.commit(repo.path, "reader.py", "print('read')\n", "Add the reader")  # the board leaves out deleted files
    env.commit(repo.path, ".factory/fixes/current-help.json", json.dumps(saved), "Keep help review decisions")
    repo.git("push", "-q", "origin", "main")
    repo.git("switch", "-q", "-c", "fix/unmerged-help")
    env.commit(repo.path, ".factory/fixes/current-help.json", json.dumps({**saved, "known": []}),
               "An unfinished help edit")
    repo.git("switch", "-q", "main")
    pr = {"number": 11, "headRefName": branch, "headRefOid": head, "baseRefName": "main",
          "state": "MERGED", "isDraft": False, "title": "Readers see a greeting", "body": "",
          "mergedAt": at.isoformat(), "mergedBy": {"login": "merger", "name": "Human Merger"},
          "author": {"login": "writer", "name": "Original Writer"},
          "url": "https://github.com/acme/shop/pull/11"}
    (repo.bin / "historical-prs.json").write_text(json.dumps([pr]), "utf-8")
    (repo.bin / "historical-checks.json").write_text("{}", "utf-8")
    github = GITHUB.replace('prs = json.loads(store.read_text("utf-8"))', '''prs = json.loads(store.read_text("utf-8"))
if args and args[0] == "api" and any("/pulls?" in arg for arg in args):
    for pr in prs:
        if pr["state"] == "MERGED":
            print(json.dumps({"number": pr["number"], "headRefName": pr["headRefName"]}))
    sys.exit(0)''')
    fallback = GH_STUB.format(python=sys.executable).split("\n", 1)[1]
    _install(repo.bin, "gh", "#!" + sys.executable + "\n" + github + fallback)
    for name in ("FORGE_NOW", "GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.setenv(name, NOW.isoformat())
    if previous:
        upgraded = up.run(RELEASE)
        assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    return repo, known, item


def test_4_board_lists_kept_review_problems_since_adoption(kept_history):
    repo, known, item = kept_history
    issues = board(repo)["known_issues"]
    assert {row["title"] for row in issues} == {
        "Add another example", "Keep the short wording", "Explain short greetings", "Older greeting has no example"}
    by_title = {row["title"]: row for row in issues}
    for entry in known[:2]:
        assert by_title[entry["title"]] == {"item": "current-help", **{
            field: entry[field] for field in ("file", "line", "title", "gain", "work", "harm", "reason")},
            "kept": entry["outcome"]}
    for title, line, scores, kept in [
        ("Explain short greetings", 1, (3, 4, 2), "follow-up"),
        ("Older greeting has no example", 2, (None, None, None), "lived with")]:
        row = by_title[title]
        assert (row["item"], row["file"], row["line"], row["kept"]) == (item, "greeting.py", line, kept)
        assert tuple(row[field] for field in ("gain", "work", "harm")) == scores
        assert row["reason"], row


def test_14_board_reads_each_merged_pull_request_once(kept_history, monkeypatch, tmp_path, request):
    # A minute-cache regression would preserve the JSON but repeat every network
    # fetch. Trace real Git to observe that distinct board-refresh contract.
    repo, _, _ = kept_history
    previous = request.node.callspec.params["kept_history"]
    fetches = []
    for seconds in (0, 86401):
        trace = tmp_path / f"git-{seconds}.jsonl"
        monkeypatch.setenv("FORGE_NOW", (NOW + timedelta(seconds=seconds)).isoformat())
        monkeypatch.setenv("GIT_TRACE2_EVENT", trace.as_posix())
        issues = board(repo)["known_issues"]
        assert any(row["item"] == "old-greeting" for row in issues)
        events = [json.loads(line) for line in trace.read_text("utf-8").splitlines()]
        fetches.append([event["argv"] for event in events if event.get("event") == "start"
                        and "fetch" in event.get("argv", [])
                        and "refs/pull/11/head" in event["argv"]])
    # Upgrade now fills the adopted repo before its first board read. A new
    # repo still fetches on demand. Expiring the aggregate must never refetch
    # either repo's immutable pull-request evidence.
    assert len(fetches[0]) == (0 if previous else 1), fetches
    assert fetches[1] == [], fetches
