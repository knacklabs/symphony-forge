"""A Codex turn that fails because the model is at capacity is retried with backoff.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import re

from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401

STORY = "a-codex-turn-that-fails-because-the-mode"


def _waits(stdout: str) -> list[float]:
    return [float(wait) for wait in re.findall(r"tries the turn again in ([\d.]+) seconds", stdout)]


def test_1_capacity_failure_is_retried_with_backoff_before_reporting(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    monkeypatch.setenv("FORGE_CODEX_RETRY_WAIT", "0.1")

    # Codex is at capacity for two turns, then has room: Forge waits longer each time, sends the
    # same turn again on the same conversation, and the round completes.
    monkeypatch.setenv("STUB_CODEX_OVERLOADED", "2")
    built = repo.forge("work", "BOARD/PAGE")
    assert built.returncode == 0, built.stdout + built.stderr
    turns = _sent(calls, "turn/start")
    assert len(turns) == 3 and len({repr(turn["input"]) for turn in turns}) == 1
    assert len(_sent(calls, "thread/start")) == 1
    assert _waits(built.stdout) == [0.1, 0.2]
    assert "Codex ended the turn: completed" in built.stdout

    # Still at capacity after every retry: Forge reports the failure as before.
    monkeypatch.setenv("STUB_CODEX_OVERLOADED", "99")
    before = len(_sent(calls, "turn/start"))
    failed = repo.forge("work", "BOARD/PAGE")
    assert failed.returncode != 0
    assert "Codex reported it failed" in failed.stderr
    assert len(_sent(calls, "turn/start")) - before == 4
    assert _waits(failed.stdout) == [0.1, 0.2, 0.4]

    # Any other failure is reported at once, with no retry.
    monkeypatch.setenv("STUB_CODEX_OVERLOADED", "0")
    monkeypatch.setenv("STUB_CODEX_STATUS", "failed")
    before = len(_sent(calls, "turn/start"))
    plain = repo.forge("work", "BOARD/PAGE")
    assert "Codex reported it failed" in plain.stderr
    assert len(_sent(calls, "turn/start")) - before == 1 and not _waits(plain.stdout)
