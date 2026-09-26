"""Codex workers pick up where they left off: a later forge work continues the item's conversation.

The stand-in Codex app-server here keeps its conversations in threads.json beside itself, as Codex
keeps them in its home, so a second app-server, in a later forge work, resumes or reads what the
first one left. The test edits that file to set what Codex reports. STUB_CODEX_STATUS=hold leaves
a turn in progress, "starting" leaves one in progress before Codex answers that it started it,
"vanish" exits instead of answering a read, "error" fails the read with an
internal error, and "unmaterialized" fails it as Codex does when it can't load a conversation's
history, naming the conversation's id.
Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import _install
from test_codex_record import _crash, _down, _saved
from test_codex_worker import (NOW, SOL, _codex_repo, _lines, _sent, _stub, _toml,  # noqa: F401
                               sdk_data)
from test_task import DOC, story

STORY = "FORGE-WARM-1"
FIX = {**SOL, "effort": "high"}
MODELS = {"build": SOL, "fix": FIX, "lite": {"model": "gpt-6-sol", "effort": "low"}}
# What [models.fix] becomes on the continued conversation: Codex's own names for those settings.
FIX_CONFIG = {"model": "gpt-6-sol", "model_reasoning_effort": "high",
              "agents.default_subagent_model": "gpt-6-luna",
              "agents.default_subagent_reasoning_effort": "max"}
LARGE = 200 * 1024

RESUMING = r'''
import json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
STORE, LOG = HERE / "threads.json", HERE / "codex-app-server.jsonl"


def log(**entry):
    with open(LOG, "a", encoding="utf-8") as out:
        out.write(json.dumps(entry) + "\n")


def save(threads):
    """Through a temporary file and a rename: Forge may end this at any moment once a turn ends,
    and a half-written store would read as empty."""
    (HERE / "threads.tmp").write_text(json.dumps(threads), encoding="utf-8")
    os.replace(HERE / "threads.tmp", STORE)


def send(**message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def thread(id, saved):
    turns = [{"id": turn, "items": [], "status": status} for turn, status in saved["turns"].items()]
    return {"id": id, "cliVersion": "0.156.1", "createdAt": 0, "updatedAt": 0, "cwd": saved["cwd"],
            "ephemeral": False, "modelProvider": "openai", "preview": "", "sessionId": "stub",
            "source": "appServer", "status": {"type": "idle"}, "turns": turns}


def main():
    if sys.argv[1:] == ["--version"]:
        print("codex-cli 0.156.1")
        return
    log(pid=os.getpid(), args=sys.argv[1:])
    for line in sys.stdin:
        message = json.loads(line)
        method, params = message.get("method"), message.get("params") or {}
        log(method=method, params=params)
        if method is None or "id" not in message:
            continue
        if method == "initialize":
            send(id=message["id"], result={"userAgent": "codex_app_server/0.156.1",
                                           "serverInfo": {"name": "codex", "version": "0.156.1"}})
            continue
        threads = json.loads(STORE.read_text("utf-8")) if STORE.exists() else {}
        id = params.get("threadId") or f"thr-stub-{len(threads) + 1}"
        saved = threads.setdefault(id, {"cwd": params.get("cwd"), "turns": {}}) \
            if method == "thread/start" else threads.get(id)
        if saved is None:  # as Codex says it: a read and a resume word it differently
            send(id=message["id"], error={"code": -32600, "message": "thread not loaded: " + id
                                          if method == "thread/read" else
                                          "no rollout found for " + id})
            continue
        result = {}
        if method in ("thread/start", "thread/resume"):
            result = {"approvalPolicy": "never", "approvalsReviewer": "user", "cwd": saved["cwd"],
                      "model": "stub-model", "modelProvider": "openai",
                      "sandbox": {"type": "dangerFullAccess"}, "thread": thread(id, saved)}
        elif method == "thread/read":
            if os.environ.get("STUB_CODEX_STATUS") == "vanish":  # gone before it answers
                return
            if os.environ.get("STUB_CODEX_STATUS") == "error":  # a server fault, not a missing one
                send(id=message["id"], error={"code": -32603, "message": "stub: store is busy"})
                continue
            if os.environ.get("STUB_CODEX_STATUS") == "unmaterialized":
                send(id=message["id"], error={"code": -32600, "message": f"thread {id} is not "
                     "materialized yet; includeTurns is unavailable before first user message"})
                continue
            result = {"thread": thread(id, saved)}
        elif method == "turn/start":
            turn = f"turn-stub-{sum(len(each['turns']) for each in threads.values()) + 1}"
            saved["turns"][turn] = "inProgress"
            save(threads)
            if os.environ.get("STUB_CODEX_COMMIT"):  # the worker commits before Forge hears more
                name = os.environ["STUB_CODEX_COMMIT"]
                pathlib.Path(saved["cwd"], name).write_text("BUILT = True\n", encoding="utf-8")
                for args in (["add", name], ["commit", "-q", "-m", "Build the page"]):
                    subprocess.run(["git", *args], cwd=saved["cwd"], check=True)
            if os.environ.get("STUB_CODEX_STATUS") == "starting":  # started, not yet answered
                time.sleep(120)
                return
            send(id=message["id"], result={"turn": {"id": turn, "items": [],
                                                    "status": "inProgress"}})
            send(method="turn/started", params={"threadId": id, "turn": {
                "id": turn, "items": [], "status": "inProgress"}})
            if os.environ.get("STUB_CODEX_STATUS") == "hold":  # stuck, as a crash would leave it
                time.sleep(120)
                return
            said = {"type": "agentMessage", "id": "msg-" + turn,
                    "text": f"stub codex: {turn} on {id}"}
            send(method="item/completed", params={"threadId": id, "turnId": turn, "item": said})
            saved["turns"][turn] = "completed"
            save(threads)
            send(method="turn/completed", params={"threadId": id, "turn": {
                "id": turn, "items": [], "status": "completed"}})
        save(threads)
        if method != "turn/start":
            send(id=message["id"], result=result)


main()
'''


def _resuming(repo, monkeypatch, sdk_data: Path) -> tuple[Path, Path, Path]:
    """Codex workers with the story approved, BOARD/PAGE started, a fix kind of its own, and the
    stand-in app-server whose conversations outlive it (run by this Python, so the command Forge
    records at its start stays its command). Returns the task's folder, the app-server's log and
    the item's turn log."""
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{RESUMING}")
    version = repo.forge("--version").stdout.split()[-1]
    (folder / "forge.toml").write_text(_toml(version, "codex", MODELS), encoding="utf-8")
    repo.git("commit", "-q", "-am", "Think harder in fix rounds", cwd=folder)
    return folder, calls, repo.path / ".git" / "forge" / "threads" / "task" / "BOARD" / "PAGE.log"


def _text(calls: Path) -> str:
    """What the last turn told Codex."""
    return _sent(calls, "turn/start")[-1]["input"][0]["text"]


def _holding(repo, turns: Path) -> tuple[subprocess.Popen, dict]:
    """forge work BOARD/PAGE whose turn Codex never ends. Returns the call and the item's record
    once the turn's "started" line is in the turn log."""
    before = len(_lines(turns)) if turns.exists() else 0
    work = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "work", "BOARD/PAGE"],
                            cwd=repo.path, env={**os.environ, "STUB_CODEX_STATUS": "hold"},
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    for _ in range(600):
        try:  # the line may be halfway written
            if turns.exists() and len(_lines(turns)) > before:
                return work, _saved(turns.with_suffix(".json"))
        except ValueError:
            pass
        time.sleep(0.05)
    work.kill()
    pytest.fail(f"the turn never started: {work.communicate()[1]}")


def test_7_fix_rounds_continue_the_conversation(repo, monkeypatch, sdk_data):
    folder, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    # The worker commits during the first turn, before Forge hears that the turn started.
    monkeypatch.setenv("STUB_CODEX_COMMIT", "built.py")
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    monkeypatch.delenv("STUB_CODEX_COMMIT")
    assert repo.git("log", "-1", "--format=%s", cwd=folder) == "Build the page"
    start = repo.git("rev-parse", "HEAD~1", cwd=folder)  # the commit the first turn started from

    # Since that turn: a commit, an edit, a new file and an ignored one, and a serious finding.
    (folder / "notes.md").write_text("First notes\n", encoding="utf-8")
    repo.git("add", "notes.md", cwd=folder)
    repo.git("commit", "-q", "-m", "Add the notes", cwd=folder)
    with (folder / "README.md").open("a", encoding="utf-8") as readme:
        readme.write("Edited after the turn\n")
    (folder / "web").mkdir()
    (folder / "web" / "new.py").write_text("NEW_FILE = True\n", encoding="utf-8")
    (repo.path / ".git" / "info" / "exclude").write_text("secret.log\n", encoding="utf-8")
    (folder / "secret.log").write_text("IGNORED CONTENT\n", encoding="utf-8")
    state_file = folder / ".factory" / "stories" / "BOARD" / "tasks" / "PAGE.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["review"] = {"status": "blocked", "findings": [
        {"priority": "P1", "title": "Archived stories are missing", "body": "Show them too.",
         "file": "web/board.py", "line": 12}]}
    state_file.write_text(json.dumps(state), encoding="utf-8")
    commits = repo.git("log", "--oneline", f"{start}..HEAD", cwd=folder)

    # The fix round continues the same conversation, renamed Fix, on the fix kind's models, with
    # full access and approvals "never"; no new conversation starts.
    fixed = repo.forge("work", "BOARD/PAGE")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    assert len(_sent(calls, "thread/start")) == 1
    [resume] = _sent(calls, "thread/resume")
    assert (resume["threadId"], resume["config"]) == ("thr-stub-1", FIX_CONFIG)
    assert (resume["sandbox"], resume["approvalPolicy"]) == ("danger-full-access", "never")
    assert Path(resume["cwd"]).resolve() == folder.resolve()
    assert [named["name"] for named in _sent(calls, "thread/name/set")] == [
        "Build · BOARD/PAGE · The page", "Fix · BOARD/PAGE · The page"]
    assert "stub codex: turn-stub-2 on thr-stub-1" in fixed.stdout

    # It tells the conversation the findings, the new commits, and every change git sees since
    # the last turn started, new files included and ignored ones left out.
    text = _text(calls)
    assert "You are the worker." in text
    assert "- P1 Archived stories are missing (web/board.py:12): Show them too." in text
    assert f"The new commits:\n\n{commits}\n" in text
    assert "Add the notes" in text and "+First notes" in text
    assert "Build the page" in text and "+BUILT = True" in text
    assert "+Edited after the turn" in text and "+NEW_FILE = True" in text
    assert "IGNORED CONTENT" not in text and "secret.log" not in text
    # Git's own index is left as it was: the new file is still untracked.
    assert "?? web/" in repo.git("status", "--porcelain", cwd=folder).splitlines()

    # The turn log says it continued the conversation.
    assert _lines(turns)[-1] == {
        "conversation": "thr-stub-1", "turn": "turn-stub-2", "kind": "Fix", "continued": True,
        "fresh_start": None, "status": "completed", "started": NOW, "ended": NOW,
        "input_tokens": None, "cached_input_tokens": None, "output_tokens": None}

    # A very large change is listed by file instead of shown in full.
    (folder / "big.txt").write_text("big line\n" * (LARGE // 9 + 1), encoding="utf-8")
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    text = _text(calls)
    assert "big line" not in text
    assert "big.txt" in text and "web/new.py" in text and "README.md" in text
    (folder / "big.txt").unlink()

    # Forge starts fresh, and says why, when it can't continue the conversation.
    record = turns.with_suffix(".json")
    store = repo.bin / "threads.json"

    def fresh(why: str) -> None:
        resumed = len(_sent(calls, "thread/resume"))
        again = repo.forge("work", "BOARD/PAGE")
        assert again.returncode == 0, again.stdout + again.stderr
        assert f"Starting a new Codex conversation, because {why}." in again.stdout
        line = _lines(turns)[-1]
        assert (line["kind"], line["continued"], line["fresh_start"]) == ("Fix", False, why)
        assert _sent(calls, "thread/name/set")[-1]["name"] == "Fix · BOARD/PAGE · The page"
        assert _sent(calls, "thread/start")[-1]["config"] == FIX_CONFIG
        tried = len(_sent(calls, "thread/resume")) - resumed
        assert tried == (1 if why.startswith("Codex couldn't") else 0), why

    # It isn't recorded here.
    record.unlink()
    fresh("Forge has no record of its conversation on this machine")
    # Codex can't resume it.
    conversation = _saved(record)["conversation"]
    threads = json.loads(store.read_text(encoding="utf-8"))
    del threads[conversation]
    store.write_text(json.dumps(threads), encoding="utf-8")
    fresh(f"Codex couldn't resume its conversation: no rollout found for {conversation}")
    # It was started in another checkout.
    moved = folder.with_name("moved-BOARD-PAGE")
    repo.git("worktree", "move", str(folder), str(moved))
    fresh(f"its conversation was started in another checkout, {folder}")
    # Its history was rewritten underneath it.
    repo.git("commit", "-q", "--amend", "-m", "Reworded", cwd=moved)
    fresh("the branch's history was rewritten under its conversation")
    # With none of those, the next call continues the conversation again.
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _lines(turns)[-1]["continued"] is True

    # The history is rewritten again and the new conversation's first turn crashes: nothing
    # rewrote that conversation's own history, so the next call continues it.
    repo.git("commit", "-q", "--amend", "-m", "Reworded again", cwd=moved)
    work, saved = _holding(repo, turns)
    _crash(work, saved)
    held = _lines(turns)[-1]
    threads = json.loads(store.read_text(encoding="utf-8"))
    threads[held["conversation"]]["turns"][held["turn"]] = "interrupted"
    store.write_text(json.dumps(threads), encoding="utf-8")
    again = repo.forge("work", "BOARD/PAGE")
    assert again.returncode == 0, again.stdout + again.stderr
    assert "Starting a new Codex conversation" not in again.stdout
    assert _sent(calls, "thread/resume")[-1]["threadId"] == held["conversation"]
    assert (_lines(turns)[-1]["conversation"], _lines(turns)[-1]["continued"]) == (
        held["conversation"], True)


def test_8_changed_approval_waits_for_a_new_one(repo, monkeypatch, sdk_data):
    folder, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    assert repo.forge("work", "BOARD/PAGE").returncode == 0

    changed = DOC.replace("Anyone can open", "Anyone can print")
    head, said = repo.git("rev-parse", "HEAD", cwd=folder), len(_stub(calls))

    def brief_refused() -> None:
        """forge work refuses to brief the worker from the checkout's story doc, which isn't the
        approved one, before it records any status or starts Codex."""
        refused = repo.forge("work", "BOARD/PAGE")
        assert refused.stderr == (
            '"What changes for you" or "Done when" in the story doc of BOARD/PAGE\'s checkout '
            "isn't what story BOARD approved, so Forge sends no brief from it.\n"
            f"Next: git -C {folder} checkout story/BOARD -- plans/BOARD.md, commit it, then "
            "forge work BOARD/PAGE\n")
        assert repo.git("rev-parse", "HEAD", cwd=folder) == head and len(_stub(calls)) == said

    # The approved part changes in the task's own checkout, which the brief is made from.
    (folder / "plans" / "BOARD.md").write_text(changed, encoding="utf-8")
    brief_refused()
    repo.git("checkout", "--", "plans/BOARD.md", cwd=folder)

    # The approval is gone and the story doc changed: an earlier approval doesn't carry over, so
    # forge work refuses before it records any status or starts Codex.
    story(repo, doc=changed, approved=None)
    unapproved = repo.forge("work", "BOARD/PAGE")
    assert unapproved.stderr == "Story BOARD is not approved yet.\nNext: forge next\n"
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and len(_stub(calls)) == said
    # The removal reaches the task's checkout too, so no copy of the old approval is left.
    kept = folder / ".factory" / "stories" / "BOARD" / "story.json"
    old = kept.read_text(encoding="utf-8")
    kept.write_text(json.dumps({**json.loads(old), "approval": None}), encoding="utf-8")
    unapproved = repo.forge("work", "BOARD/PAGE")
    assert unapproved.stderr == "Story BOARD is not approved yet.\nNext: forge next\n"
    assert len(_stub(calls)) == said
    kept.write_text(old, encoding="utf-8")

    # Both records are deleted, the story's and the checkout's copy: a story that had one still
    # needs its approval, so forge work refuses the same way before it starts anything.
    repo.git("checkout", "-q", "story/BOARD")
    repo.git("rm", "-q", ".factory/stories/BOARD/story.json")
    repo.git("commit", "-q", "-m", "Drop the story's record")
    repo.git("checkout", "-q", "main")
    kept.unlink()
    unapproved = repo.forge("work", "BOARD/PAGE")
    assert unapproved.stderr == "Story BOARD is not approved yet.\nNext: forge next\n"
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and len(_stub(calls)) == said
    kept.write_text(old, encoding="utf-8")

    # A task branch made by hand, for a story that never had a record: no approval, so forge work
    # refuses the same way before it records any status or starts Codex.
    repo.git("checkout", "-q", "-b", "story/HAND")
    repo.write("plans/HAND.md", DOC)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "A story no one approved")
    repo.git("checkout", "-q", "main")
    hand = repo.path.parent / "repo-HAND-PAGE"
    repo.git("worktree", "add", "-q", "-b", "task/HAND-PAGE", str(hand), "story/HAND")
    hand_head = repo.git("rev-parse", "HEAD", cwd=hand)
    unapproved = repo.forge("work", "HAND/PAGE")
    assert unapproved.stderr == "Story HAND is not approved yet.\nNext: forge next\n"
    assert repo.git("rev-parse", "HEAD", cwd=hand) == hand_head and len(_stub(calls)) == said

    # The story's approved part changes: forge work refuses before it records any status or
    # starts Codex, until the change is approved again.
    story(repo, doc=changed, approved=DOC)
    refused = repo.forge("work", "BOARD/PAGE")
    assert refused.stderr == ('"What changes for you" or "Done when" of story BOARD changed after '
                              "its approval, so it needs a new approval.\nNext: forge next\n")
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and len(_stub(calls)) == said

    # Once approved again, the checkout's old story doc isn't sent under the new approval; once the
    # approved doc is in the checkout, the conversation started under the old approval isn't
    # continued.
    story(repo, doc=changed, approved=changed)
    brief_refused()
    repo.git("checkout", "story/BOARD", "--", "plans/BOARD.md", cwd=folder)
    repo.git("commit", "-q", "-m", "Take the approved story doc", cwd=folder)
    again = repo.forge("work", "BOARD/PAGE")
    assert again.returncode == 0, again.stdout + again.stderr
    why = "the story's approval changed after its conversation started"
    assert f"Starting a new Codex conversation, because {why}." in again.stdout
    assert _sent(calls, "thread/resume") == [] and len(_sent(calls, "thread/start")) == 2
    assert (_lines(turns)[-1]["continued"], _lines(turns)[-1]["fresh_start"]) == (False, why)

    # Under the new approval, the next call continues the new conversation.
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert [call["threadId"] for call in _sent(calls, "thread/resume")] == ["thr-stub-2"]

    # The approved part changes in the story's own worktree, not yet committed: that is the doc the
    # next approval reads, so forge work refuses before it records any status or starts Codex.
    planning = repo.path.parent / "repo-story-BOARD"
    repo.git("worktree", "add", "-q", str(planning), "story/BOARD")
    (planning / "plans" / "BOARD.md").write_text(DOC, encoding="utf-8")
    head, said = repo.git("rev-parse", "HEAD", cwd=folder), len(_stub(calls))
    refused = repo.forge("work", "BOARD/PAGE")
    assert refused.stderr == ('"What changes for you" or "Done when" of story BOARD changed after '
                              "its approval, so it needs a new approval.\nNext: forge next\n")
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and len(_stub(calls)) == said
    repo.git("worktree", "remove", "--force", str(planning))

    # Once a task has merged, the default branch holds the story doc and that approval, but the
    # story's own branch, where approvals are committed, still decides: a change there refuses
    # before any status or Codex call, and its new approval isn't sent under the old doc.
    repo.git("checkout", "story/BOARD", "--", "plans/BOARD.md", ".factory/stories/BOARD")
    repo.git("commit", "-q", "-m", "The first task merged")
    repo.git("push", "-q", "origin", "main")
    head, said = repo.git("rev-parse", "HEAD", cwd=folder), len(_stub(calls))
    story(repo, doc=DOC, approved=changed)
    refused = repo.forge("work", "BOARD/PAGE")
    assert refused.stderr == ('"What changes for you" or "Done when" of story BOARD changed after '
                              "its approval, so it needs a new approval.\nNext: forge next\n")
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and len(_stub(calls)) == said
    story(repo, doc=DOC, approved=DOC)
    brief_refused()

    # The story's branch still exists but its approved doc is deleted there: the default branch's
    # older doc and approval, which match the task's checkout, don't stand in for it, so forge work
    # refuses before it records any status or starts Codex.
    story(repo, doc=changed, approved=changed)
    repo.git("checkout", "-q", "story/BOARD")
    repo.git("rm", "-q", "plans/BOARD.md")
    repo.git("commit", "-q", "-m", "Drop the story doc")
    repo.git("checkout", "-q", "main")
    refused = repo.forge("work", "BOARD/PAGE")
    assert refused.stderr == ('"What changes for you" or "Done when" of story BOARD changed after '
                              "its approval, so it needs a new approval.\nNext: forge next\n")
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and len(_stub(calls)) == said


def test_9_crash_recovery_reads_the_conversation_back(repo, monkeypatch, sdk_data):
    folder, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    store = repo.bin / "threads.json"
    lock = turns.with_suffix(".lock")

    def report(turn: str, status: str | None) -> None:
        """Make Codex report this status for the turn, or no such turn at all."""
        threads = json.loads(store.read_text(encoding="utf-8"))
        if status is None:
            del threads["thr-stub-1"]["turns"][turn]
        else:
            threads["thr-stub-1"]["turns"][turn] = status
        store.write_text(json.dumps(threads), encoding="utf-8")

    # forge work crashes mid-turn, leaving its Codex processes and no end line.
    work, saved = _holding(repo, turns)
    stub = saved["app_server"]["pid"]
    _crash(work, saved)
    assert lock.exists() and "status" not in _lines(turns)[-1]
    held = _lines(turns)[-1]

    # The next forge work stops the leftover processes, then reads the conversation back. Codex
    # goes away before it says how the turn ended, so forge work refuses before it records any
    # status: it can't tell whether the turn still runs.
    head = repo.git("rev-parse", "HEAD", cwd=folder)
    monkeypatch.setenv("STUB_CODEX_STATUS", "vanish")
    unread = repo.forge("work", "BOARD/PAGE")
    monkeypatch.delenv("STUB_CODEX_STATUS")
    log = repo.path / ".git" / "forge" / "work-BOARD-PAGE.log"
    assert unread.stderr == ("Codex didn't say how the last turn of BOARD/PAGE ended, so Forge "
                             f"starts no second one; its log is {log}.\n"
                             "Next: forge work BOARD/PAGE\n")
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and _lines(turns)[-1] == held
    assert _down(stub) and _down(saved["driver"]["pid"])

    # Codex fails the read for another reason than a missing conversation: that proves nothing
    # about the turn, so forge work refuses the same way instead of logging it lost.
    monkeypatch.setenv("STUB_CODEX_STATUS", "error")
    failed = repo.forge("work", "BOARD/PAGE")
    monkeypatch.delenv("STUB_CODEX_STATUS")
    assert failed.stderr == unread.stderr
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and _lines(turns)[-1] == held

    # Nor is a failed history read, though its message names the conversation.
    monkeypatch.setenv("STUB_CODEX_STATUS", "unmaterialized")
    unloaded = repo.forge("work", "BOARD/PAGE")
    monkeypatch.delenv("STUB_CODEX_STATUS")
    assert unloaded.stderr == unread.stderr
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and _lines(turns)[-1] == held

    # Codex still says the turn is running: forge work refuses again, so two turns never run.
    running = repo.forge("work", "BOARD/PAGE")
    assert running.stderr == ("Codex says the last turn of BOARD/PAGE is still running, so Forge "
                              "starts no second one.\nNext: wait for it to end in the Codex app, "
                              "then forge work BOARD/PAGE\n")
    assert [read["threadId"] for read in _sent(calls, "thread/read")] == ["thr-stub-1"] * 4
    assert repo.git("rev-parse", "HEAD", cwd=folder) == head and _lines(turns)[-1] == held
    assert not lock.exists() and len(_sent(calls, "turn/start")) == 1

    # Once Codex reports the turn's end, it is logged with that status, and the work goes on in
    # the same conversation.
    report(held["turn"], "interrupted")
    recovered = repo.forge("work", "BOARD/PAGE")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    lines = _lines(turns)
    assert lines[-3] == {**held, "continued": False, "fresh_start": "first turn",
                         "status": "interrupted", "ended": NOW, "input_tokens": None,
                         "cached_input_tokens": None, "output_tokens": None}
    assert lines[-1]["status"] == "completed" and lines[-1]["continued"] is True
    assert [call["threadId"] for call in _sent(calls, "thread/resume")] == ["thr-stub-1"]

    # A crashed turn Codex reports no status for is logged as lost, never as finished.
    work, saved = _holding(repo, turns)
    _crash(work, saved)
    held = _lines(turns)[-1]
    report(held["turn"], None)
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _down(saved["app_server"]["pid"])
    lines = _lines(turns)
    assert lines[-3] == {**held, "continued": True, "fresh_start": None, "status": "lost",
                         "ended": NOW, "input_tokens": None, "cached_input_tokens": None,
                         "output_tokens": None}

    # forge work crashes after Codex started a turn but before Forge logged its "started" line.
    # The next one still reads the conversation back and refuses while Codex says that turn runs.
    conversation = _saved(turns.with_suffix(".json"))["conversation"]
    before = len(_sent(calls, "turn/start"))
    logged = _lines(turns)

    def unseen() -> list[str]:
        """The turns Codex says still run."""
        threads = json.loads(store.read_text(encoding="utf-8"))
        return [turn for turn, status in threads[conversation]["turns"].items()
                if status == "inProgress"]

    work = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "work", "BOARD/PAGE"],
                            cwd=repo.path, env={**os.environ, "STUB_CODEX_STATUS": "starting"},
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    for _ in range(600):
        if unseen():
            break
        time.sleep(0.05)
    else:
        work.kill()
        pytest.fail(f"the turn never started: {work.communicate()[1]}")
    saved = _saved(turns.with_suffix(".json"))
    _crash(work, saved)
    assert _lines(turns) == logged
    running = repo.forge("work", "BOARD/PAGE")
    assert running.stderr == ("Codex says the last turn of BOARD/PAGE is still running, so Forge "
                              "starts no second one.\nNext: wait for it to end in the Codex app, "
                              "then forge work BOARD/PAGE\n")
    assert len(_sent(calls, "turn/start")) == before + 1 and _lines(turns) == logged
    assert _down(saved["app_server"]["pid"])

    # Once Codex reports that turn's end, it is logged with that status and the work goes on.
    [held] = unseen()
    threads = json.loads(store.read_text(encoding="utf-8"))
    threads[conversation]["turns"][held] = "interrupted"
    store.write_text(json.dumps(threads), encoding="utf-8")
    recovered = repo.forge("work", "BOARD/PAGE")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    lines = _lines(turns)
    assert lines[-3] == {"conversation": conversation, "turn": held, "kind": "Fix",
                         "started": None, "continued": True, "fresh_start": None,
                         "status": "interrupted", "ended": NOW, "input_tokens": None,
                         "cached_input_tokens": None, "output_tokens": None}
    assert (lines[-1]["conversation"], lines[-1]["status"]) == (conversation, "completed")

    # A crashed turn whose whole conversation Codex no longer has is logged as lost too, and the
    # work starts a new conversation, saying why.
    work, saved = _holding(repo, turns)
    _crash(work, saved)
    held = _lines(turns)[-1]
    threads = json.loads(store.read_text(encoding="utf-8"))
    del threads[held["conversation"]]
    store.write_text(json.dumps(threads), encoding="utf-8")
    gone = repo.forge("work", "BOARD/PAGE")
    assert gone.returncode == 0, gone.stdout + gone.stderr
    lines = _lines(turns)
    assert (lines[-3]["turn"], lines[-3]["status"]) == (held["turn"], "lost")
    assert (lines[-1]["continued"], lines[-1]["status"]) == (False, "completed")
