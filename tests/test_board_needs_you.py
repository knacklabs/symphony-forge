"""Needs you lists every item waiting on a person, oldest first, the same on every machine.

Real Forge commands and git build every wait; only GitHub, the reviewer, the reader and the
worker are stubs. Board and next output is all the tests read.
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone

import pytest

import conftest
from test_board_counts import ONE_PART, board, clock, configure, github, read_story
from test_close import CLEAN, STORY_DOC, approve_story, blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_hotspot_stop import rounds, seed
from test_story import READER, worktree
from test_worker import install_claude

STORY = "FORGE-BOARD-2"
FIX = {"kind": "fix", "done_when": "It works"}


def needs(repo):
    return [(entry["id"], entry["reason"]) for entry in board(repo)["team"]["needs_you"]]


def share(env, prs, name, number, branch=None):
    """GitHub now holds the item's pull request with the body Forge last sent it."""
    sent = [call for call in env.gh_calls("pr") if call[1] in ("create", "edit")]
    branch = branch or f"fix/{name}"
    prs[name] = {"number": number, "headRefName": branch, "state": "OPEN", "title": name,
                 "body": body(sent[-1]), "isDraft": False, "mergedAt": None, "mergedBy": None,
                 "author": {"login": "forge-test", "name": "Forge Test"},
                 "headRefOid": env.repo.git("ls-remote", "origin", f"refs/heads/{branch}").split()[0],
                 "url": f"https://github.com/acme/shop/pull/{number}"}
    published(env, prs)


def published(env, prs):
    github(env, list(prs.values()))
    for cache in env.tmp.rglob("prs-cache.json"):
        cache.unlink()


def older(env, prs, name):
    """The pull request reads as one an earlier release closed ready, with no merge wait recorded."""
    def strip(match):
        data = json.loads(match[1])
        data["events"] = [event for event in data["events"] if event.get("reason") != "merge"]
        return "<!-- forge:time-record " + json.dumps(data, separators=(",", ":")) + " -->"
    prs[name]["body"] = re.sub(r"<!-- forge:time-record (\{.*?\}) -->", strip, prs[name]["body"], flags=re.S)
    log = env.repo.path / ".git/forge/events.jsonl"
    log.write_text("".join(line + "\n" for line in log.read_text("utf-8").splitlines()
                           if not (json.loads(line).get("item") == name and json.loads(line).get("reason") == "merge")),
                   "utf-8")
    published(env, prs)


@pytest.mark.parametrize("case", ["waits", "blocking-problems", "size-choice"])
@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_2_needs_you_lists_every_wait_oldest_first_on_every_machine(env, monkeypatch, previous, case):
    client(env, previous)
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    configure(env, "human")
    if case == "blocking-problems":
        blocking_problems(env)
        return
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8")
               + 'models.lite = { model = "sonnet", effort = "medium" }\n')
    env.repo.git("push", "-q", "origin", "main")
    if case == "size-choice":
        size_choice(env)
        return
    seed(env, "src/a.py")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    prs = {}

    # A plan read and waiting for approval.
    clock(monkeypatch, now)
    read_story(env.repo, "WAIT", ONE_PART)
    env.repo.git("push", "-q", "origin", "story/WAIT")
    # Three blocked closes stop the review loop for a person's choice.
    clock(monkeypatch, now + timedelta(minutes=1))
    _, loop = env.start("loop", "fix/loop", ".factory/fixes/loop.json", {**FIX, "why": "Loop"}, {"loop.py": "x\n"})
    rounds(env, "loop", loop, ["src/a.py"] * 3)
    share(env, prs, "loop", 1)
    # A close ending ready in a repo where a human merges.
    clock(monkeypatch, now + timedelta(minutes=2))
    env.reviews(CLEAN)
    env.start("human", "fix/human", ".factory/fixes/human.json", {**FIX, "why": "Human"}, {"human.py": "x\n"})
    assert env.close("human").returncode == 0
    share(env, prs, "human", 2)
    # A worker's question on a fix with a pull request.
    install_claude(env.repo)
    _, asks = env.start("asks", "fix/asks", ".factory/fixes/asks.json",
                        {**FIX, "why": "Asks", "round": 1}, {"asks.py": "x\n"})
    assert env.close("asks").returncode == 0
    share(env, prs, "asks", 3)
    if previous:  # an earlier release's worker answered a question without recording its end
        with (env.repo.path / ".git/forge/events.jsonl").open("a", encoding="utf-8") as log:
            for event in ({"id": "old-question", "event": "worker question", "question": "Question: Keep it?",
                           "at": (now + timedelta(minutes=2)).isoformat()},
                          {"id": "old-round", "event": "run start", "kind": "worker", "round": 2,
                           "at": (now + timedelta(minutes=2, seconds=30)).isoformat()}):
                log.write(json.dumps({**event, "item": "asks"}) + "\n")
    clock(monkeypatch, now + timedelta(minutes=3))
    monkeypatch.setenv("STUB_CLAUDE_RESULT", "\n\nQuestion: May I reuse the basket parser?")
    asked = env.repo.forge("work", "asks")
    assert asked.returncode == 0 and "May I reuse the basket parser?" in asked.stdout, asked.stderr
    monkeypatch.delenv("STUB_CLAUDE_RESULT")
    share(env, prs, "asks", 3)
    # A merge conflict close stopped on, on the fix's first close: it opens the pull request.
    clock(monkeypatch, now + timedelta(minutes=4))
    env.commit(env.repo.path, "clash.py", "print('old')\n")
    env.repo.git("push", "-q", "origin", "main")
    _, clash = env.start("clash", "fix/clash", ".factory/fixes/clash.json", {**FIX, "why": "Clash"},
                         {"clash.py": "print('branch')\n"})
    env.commit(env.repo.path, "clash.py", "print('main')\n")
    env.repo.git("push", "-q", "origin", "main")
    conflicted = env.close("clash")
    assert conflicted.returncode == 1 and "conflicts in clash.py" in conflicted.stderr
    share(env, prs, "clash", 4)
    # An older ready pull request with no merge wait recorded still waits on its human merge.
    env.start("legacy", "fix/legacy", ".factory/fixes/legacy.json", {**FIX, "why": "Legacy"}, {"legacy.py": "x\n"})
    assert env.close("legacy").returncode == 0
    share(env, prs, "legacy", 5)
    older(env, prs, "legacy")

    clock(monkeypatch, now + timedelta(minutes=5))
    order = [("WAIT", "approval"), ("loop", "review loop"), ("human", "merge"),
             ("asks", "worker question"), ("clash", "conflict"), ("legacy", "merge")]
    machine_a = env.repo.path
    machine_b = env.tmp / "needs-machine-b"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(machine_b))
    for where in (machine_a, machine_b):
        env.repo.path = where
        team = board(env.repo)["team"]
        assert [(entry["id"], entry["reason"]) for entry in team["needs_you"]] == order, where
        assert [entry["waited_seconds"] for entry in team["needs_you"]] == [300, 240, 180, 120, 60, None], where
        assert team["needs_you"][-1]["since"] is None
        assert "6 need you" in team["sentence"]
    # Past the 30 minutes after which close records the repo's default choice, the stop still
    # waits on a person until a choice is committed.
    env.repo.path = machine_a
    clock(monkeypatch, now + timedelta(minutes=40))
    assert ("loop", "review loop") in needs(env.repo)
    clock(monkeypatch, now + timedelta(minutes=5))

    # Each clears: the approval, a choice recorded on machine B, the merge, the answer given on
    # machine B and a clean close of the resolved conflict, which then waits on a human merge only.
    env.repo.path = machine_a
    plan = {"plan": ONE_PART, "isAgent": False, "filePath": "/plans/plan.md"}
    payload = conftest._payload("PostToolUse", env.repo.path, "ExitPlanMode", {"plan": ONE_PART}, plan)
    approved = env.repo.forge("hook", "approval", input=json.dumps(payload))
    assert approved.returncode == 0, approved.stdout + approved.stderr
    env.repo.git("push", "-q", "origin", "story/WAIT")
    prs["human"].update(state="MERGED", mergedAt=(now + timedelta(minutes=5)).isoformat())
    env.repo.git("merge", "--no-edit", "-X", "ours", "origin/main", cwd=clash)
    assert env.close("clash").returncode == 0
    share(env, prs, "clash", 4)
    env.repo.path = machine_b
    env.repo.git("worktree", "add", "-q", "-b", "fix/loop", str(env.tmp / "needs-loop-b"), "origin/fix/loop")
    chosen = env.repo.forge("close", "loop", "--resolve", "narrow", "--reason", "Keep it small")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    share(env, prs, "loop", 1)
    # B, who did not open the pull request, answers the question.
    resumed = env.tmp / "needs-asks-b"
    env.repo.git("worktree", "add", "-q", "-b", "fix/asks", str(resumed), "origin/fix/asks")
    answered = env.repo.forge("work", "asks", "--note", "Yes, reuse it", cwd=resumed)
    assert answered.returncode == 0, answered.stdout + answered.stderr
    share(env, prs, "asks", 3)
    # A's own record still holds that question, yet A works on; its worker asks a second one.
    env.repo.path = machine_a
    monkeypatch.setenv("STUB_CLAUDE_RESULT", "\n\nQuestion: Should the parser keep comments?")
    worked = env.repo.forge("work", "asks")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    monkeypatch.delenv("STUB_CLAUDE_RESULT")
    share(env, prs, "asks", 3)
    clock(monkeypatch, now + timedelta(minutes=7))
    for where in (machine_a, machine_b):
        env.repo.path = where
        # Machine A's stale stop and its own log of the first question do not bring them back.
        assert needs(env.repo) == [("asks", "worker question"), ("clash", "merge"), ("legacy", "merge")], where
    # B answers the second question, and both merges happen: nothing needs a person anywhere.
    env.repo.path = machine_b
    again = env.repo.forge("work", "asks", "--note", "Keep them", cwd=resumed)
    assert again.returncode == 0, again.stdout + again.stderr
    share(env, prs, "asks", 3)
    for name in ("clash", "legacy"):
        prs[name].update(state="MERGED", mergedAt=(now + timedelta(minutes=7)).isoformat())
    published(env, prs)
    for where in (machine_a, machine_b):
        env.repo.path = where
        team = board(env.repo)["team"]
        assert team["needs_you"] == [] and "0 need you" in team["sentence"], where


def size_choice(env):
    """A teammate's part grows past its size limit on a pull request someone else opened: close
    stops it with a question and publishes it, so the opener's machine sees it too."""
    prs = {}
    item, _ = env.start_approved_task(STORY_DOC, changes={"app.py": "x = 1\n"})
    env.repo.git("merge", "-q", "--no-edit", "story/SHOP")
    env.repo.git("push", "-q", "origin", "main")
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    share(env, prs, item, 6, "task/SHOP-T1")
    machine_a = env.repo.path
    machine_b = env.tmp / "size-machine-b"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(machine_b))
    env.repo.path = machine_b
    resumed = env.tmp / "size-part-b"
    env.repo.git("worktree", "add", "-q", "-b", "task/SHOP-T1", str(resumed), "origin/task/SHOP-T1")
    env.commit(resumed, "app.py", "new = 1\n" * 401)
    stopped = env.close(item)
    assert stopped.returncode == 1 and "over its limit" in stopped.stdout + stopped.stderr, stopped.stderr
    share(env, prs, item, 6, "task/SHOP-T1")
    env.repo.path = machine_a
    assert (item, "review loop") in needs(env.repo)


def blocking_problems(env):
    """A malformed story doc and a plan behind its published copy are in Needs you in forge next's
    words, and leave once fixed."""
    approve_story(env.repo, ONE_PART, key="CART")
    plan = env.repo.path / "plans/CART.md"
    env.repo.git("merge", "-q", "--no-edit", "story/CART")
    env.commit(env.repo.path, "plans/CART.md", plan.read_text("utf-8").replace("leave.", "leave the shop."))
    env.repo.git("push", "-q", "origin", "main")
    bad = read_story(env.repo, "BAD", ONE_PART.replace("# Shoppers can save a basket", "# A bad plan", 1))
    good = (bad / "plans/BAD.md").read_text("utf-8")
    env.commit(bad, "plans/BAD.md", good.replace("| — | no |", "| OTHER/MISSING | no |"))
    following = env.repo.forge("next").stdout
    team = board(env.repo)["team"]
    found = {entry["id"]: entry for entry in team["needs_you"]}
    rows = {row["id"]: row for row in board(env.repo)["items"]}
    assert rows["CART"]["needs_person"] is True and rows["BAD"]["needs_person"] is True
    assert {key: found[key]["reason"] for key in ("CART", "BAD")} == {"CART": "blocked plan", "BAD": "blocked plan"}
    for key in ("CART", "BAD"):
        assert found[key]["detail"] in following, (found[key]["detail"], following)
    assert "OTHER/MISSING" in found["BAD"]["detail"] and found["CART"]["since"]

    env.commit(bad, "plans/BAD.md", good)
    env.repo.git("merge", "-q", "--no-edit", "main", cwd=worktree(env.repo, "story/CART"))
    assert not [entry for entry in board(env.repo)["team"]["needs_you"] if entry["reason"] == "blocked plan"]
