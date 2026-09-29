"""A worker is told to run tests in the foreground and commit before its turn ends, and forge work
warns, naming the files, when a round ends with changes left uncommitted."""
from __future__ import annotations

from test_fix_claude_workers_start_a_fresh_session_eve import FIX, _started
from test_worker import calls

STORY = "claude-workers-start-the-test-suite-in-t"
WARNING = ("Warning: the worker ended its round with changes left uncommitted, so the review "
           "won't see them:")


def test_1_the_worker_brief_says_run_tests_in_the_foreground_and_commit_before_the_turn_ends(
        repo, gh):
    log = _started(repo)

    built = repo.forge("work", FIX)

    assert built.returncode == 0, built.stdout + built.stderr
    [call] = calls(log)
    brief = " ".join(call["brief"].split())
    assert "Run tests in the foreground" in brief
    assert "Never end your turn while a command you started still runs in the background" in brief
    assert "Commit your work before your turn ends" in brief


def test_2_forge_work_warns_naming_the_files_a_round_left_uncommitted(repo, gh, monkeypatch):
    log = _started(repo)
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "login.txt")

    left = repo.forge("work", FIX)

    assert left.returncode == 0, left.stdout + left.stderr
    assert f"{WARNING} login.txt." in left.stdout

    # A round that leaves nothing uncommitted prints no warning.
    monkeypatch.delenv("STUB_CLAUDE_LEAVE")
    folder = calls(log)[0]["cwd"]
    repo.git("-C", folder, "add", "login.txt")
    repo.git("-C", folder, "commit", "-q", "-m", "Keep the login text")

    clean = repo.forge("work", FIX)

    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert WARNING not in clean.stdout
