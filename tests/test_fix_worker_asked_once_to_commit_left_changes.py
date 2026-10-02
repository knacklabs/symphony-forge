"""When a worker's round ends with changes left uncommitted, forge work continues the same
conversation once, telling the worker to run the test command in the foreground, wait and commit;
only a worker that still leaves changes uncommitted gets the warning. Claude and Codex alike."""
from __future__ import annotations

from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401 (sdk_data is a fixture)
from test_fix_claude_workers_start_a_fresh_session_eve import FIX, _session, _started
from test_worker import calls

STORY = "workers-keep-ending-their-round-while-th"
WARNING = "Warning: the worker ended its round with changes left uncommitted"
NUDGE = ("in the foreground and wait for it to finish; never leave it running in the background. "
         "Then commit your work on this branch")


def test_1_a_claude_worker_that_left_changes_uncommitted_is_asked_once_and_commits(
        repo, gh, monkeypatch):
    log = _started(repo)
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "login.txt")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "2")

    built = repo.forge("work", FIX)

    assert built.returncode == 0, built.stdout + built.stderr
    first, nudged = calls(log)
    assert _session(nudged, "--resume") == _session(first, "--session-id")
    assert NUDGE in " ".join(nudged["brief"].split())
    assert "Run the repo's test command (`pytest -q`) in the foreground" in nudged["brief"]
    assert repo.git("status", "--porcelain", "-uall", cwd=first["cwd"]) == ""
    assert repo.git("log", "-1", "--format=%s", "--name-only", cwd=first["cwd"]).split() == [
        "Worker", "round", "login.txt"]
    assert WARNING not in built.stdout


def test_2_a_claude_worker_that_never_commits_still_gets_the_warning(repo, gh, monkeypatch):
    log = _started(repo)
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "login.txt")

    left = repo.forge("work", FIX)

    assert left.returncode == 0, left.stdout + left.stderr
    assert len(calls(log)) == 2
    assert f"{WARNING}, so the review won't see them: login.txt." in left.stdout


def test_3_a_worker_that_commits_its_round_is_not_asked_again(repo, gh, monkeypatch):
    log = _started(repo)
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "login.txt")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "1")

    built = repo.forge("work", FIX)

    assert built.returncode == 0, built.stdout + built.stderr
    assert len(calls(log)) == 1 and WARNING not in built.stdout


def test_4_a_codex_worker_that_left_changes_uncommitted_is_asked_once_and_commits(
        repo, gh, monkeypatch, sdk_data):
    folder, server = _codex_repo(repo, monkeypatch, sdk_data)
    monkeypatch.setenv("STUB_CODEX_TOUCH", "login.txt")
    monkeypatch.setenv("STUB_CODEX_COMMIT_FROM", "2")

    built = repo.forge("work", "BOARD/PAGE")

    assert built.returncode == 0, built.stdout + built.stderr
    first, nudged = _sent(server, "turn/start")
    # The nudge asks Codex to resume the round's conversation (the stub can't, so it starts anew).
    assert [sent["threadId"] for sent in _sent(server, "thread/resume")] == [first["threadId"]]
    assert NUDGE in " ".join(nudged["input"][0]["text"].split())
    assert repo.git("status", "--porcelain", "-uall", cwd=folder) == ""
    assert WARNING not in built.stdout


def test_5_a_codex_worker_that_never_commits_still_gets_the_warning(
        repo, gh, monkeypatch, sdk_data):
    folder, server = _codex_repo(repo, monkeypatch, sdk_data)
    monkeypatch.setenv("STUB_CODEX_TOUCH", "login.txt")

    left = repo.forge("work", "BOARD/PAGE")

    assert left.returncode == 0, left.stdout + left.stderr
    assert len(_sent(server, "turn/start")) == 2
    assert f"{WARNING}, so the review won't see them: login.txt." in left.stdout
