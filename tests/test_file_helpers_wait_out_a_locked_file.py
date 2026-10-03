"""The test helpers that read, write and delete files under a test's temp folder wait out the
moment Windows keeps a file from them, and fail only once it stays locked for five seconds."""
from __future__ import annotations

import io
import os
import time
from pathlib import Path

import pytest

from test_codex_record import _saved
from test_codex_resume import _resuming
from test_codex_worker import _lines, _sent
from test_codex_worker import sdk_data  # noqa: F401 (a fixture)

STORY = "windows-ci-jobs-keep-failing-with-permis"


def _locked(monkeypatch, path: Path, times: float) -> list[str]:
    """Make opening or deleting path refuse as a locked file does on Windows, this many times,
    beneath the Path methods every helper uses. Returns each attempt."""
    real_open, real_unlink, tries = io.open, os.unlink, []

    def refused(what: str, target) -> None:
        if isinstance(target, (str, os.PathLike)) and Path(target) == path:  # not a descriptor
            tries.append(what)
            if len(tries) <= times:
                raise PermissionError(13, "Permission denied", str(target))

    def opening(file, *args, **kwargs):
        refused("open", file)
        return real_open(file, *args, **kwargs)

    def unlinking(target, *args, **kwargs):
        refused("unlink", target)
        return real_unlink(target, *args, **kwargs)

    monkeypatch.setattr(io, "open", opening)
    monkeypatch.setattr(os, "unlink", unlinking)
    return tries


def test_1_a_read_a_write_and_a_delete_succeed_after_a_locked_file_lets_go(tmp_path, monkeypatch):
    record = tmp_path / "threads.json"
    record.write_text("{}", encoding="utf-8")
    with monkeypatch.context() as locked:
        tries = _locked(locked, record, 2)
        record.write_text('{"turn": "inProgress"}', encoding="utf-8")
    assert tries == ["open"] * 3
    with monkeypatch.context() as locked:
        tries = _locked(locked, record, 2)
        assert record.read_text("utf-8") == '{"turn": "inProgress"}'
    assert tries == ["open"] * 3
    with monkeypatch.context() as locked:
        tries = _locked(locked, record, 2)
        record.unlink()
    assert tries == ["unlink"] * 3 and not record.exists()


def test_2_a_file_that_stays_locked_fails_after_five_seconds(tmp_path, monkeypatch):
    record = tmp_path / "threads.json"
    record.write_text("{}", encoding="utf-8")
    _locked(monkeypatch, record, float("inf"))
    began = time.monotonic()
    with pytest.raises(PermissionError):
        record.read_text("utf-8")
    assert time.monotonic() - began >= 5


def test_3_forge_work_rounds_go_on_while_their_records_refuse_twice(repo, monkeypatch, sdk_data):
    _, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    record = turns.with_suffix(".json")
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr

    # The turn log and the conversation record each refuse twice, as a file Forge is renaming
    # over does on Windows; the helpers still read both.
    with monkeypatch.context() as locked:
        tries = _locked(locked, turns, 2)
        assert _lines(turns)[-1]["status"] == "completed" and len(tries) == 3
    with monkeypatch.context() as locked:
        tries = _locked(locked, record, 2)
        assert _saved(record)["conversation"] and len(tries) == 3

    # Deleting the record waits out two refusals too, and the next round still runs.
    with monkeypatch.context() as locked:
        tries = _locked(locked, record, 2)
        record.unlink()
    assert not record.exists() and len(tries) == 3
    second = repo.forge("work", "BOARD/PAGE")
    assert second.returncode == 0, second.stdout + second.stderr
    assert _sent(calls, "turn/start")[-1]["input"][0]["text"].startswith("Fix round 2 on The page.\n")
