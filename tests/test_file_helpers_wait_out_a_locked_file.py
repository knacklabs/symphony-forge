"""The test helpers that read, write and delete files under a test's temp folder wait out the
moment Windows keeps a file from them, and fail only once it stays locked for five seconds."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from conftest import patient
from test_codex_record import _save, _saved
from test_codex_resume import _resuming
from test_codex_worker import _lines, _sent
from test_codex_worker import sdk_data  # noqa: F401 (a fixture)

STORY = "windows-ci-jobs-keep-failing-with-permis"


def _locked(monkeypatch, method: str, times: float, path: Path | None = None) -> list[int]:
    """Make Path.<method> refuse as a locked file does on Windows, this many times, on path only
    when one is given."""
    real, calls = getattr(Path, method), []

    def refuse(self, *args, **kwargs):
        if path is not None and self != path:
            return real(self, *args, **kwargs)
        calls.append(1)
        if len(calls) <= times:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, method, refuse)
    return calls


def test_1_a_read_and_a_write_succeed_after_a_locked_file_lets_go(tmp_path, monkeypatch):
    record = tmp_path / "threads.json"
    record.write_text('{"turn": "inProgress"}', encoding="utf-8")
    reads = _locked(monkeypatch, "read_text", 2)
    assert _saved(record) == {"turn": "inProgress"} and len(reads) == 3

    monkeypatch.undo()
    writes = _locked(monkeypatch, "write_text", 2)
    _save(record, {"turn": "interrupted"})
    monkeypatch.undo()
    assert _saved(record) == {"turn": "interrupted"} and len(writes) == 3


def test_2_a_file_that_stays_locked_fails_after_five_seconds(tmp_path, monkeypatch):
    record = tmp_path / "threads.json"
    record.write_text("{}", encoding="utf-8")
    _locked(monkeypatch, "read_text", float("inf"))
    began = time.monotonic()
    with pytest.raises(PermissionError):
        _saved(record)
    assert time.monotonic() - began >= 5


def test_3_forge_work_rounds_go_on_while_their_records_refuse_twice(repo, monkeypatch, sdk_data):
    _, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    record = turns.with_suffix(".json")
    first = repo.forge("work", "BOARD/PAGE")
    assert first.returncode == 0, first.stdout + first.stderr

    # The turn log and the conversation record each refuse twice, as a file Forge is renaming
    # over does on Windows; the test still reads both.
    with monkeypatch.context() as locked:
        log_reads = _locked(locked, "read_text", 2, turns)
        assert _lines(turns)[-1]["status"] == "completed" and len(log_reads) == 3
    with monkeypatch.context() as locked:
        record_reads = _locked(locked, "read_text", 2, record)
        assert _saved(record)["conversation"] and len(record_reads) == 3

    # Deleting the record waits out two refusals too, and the next round still runs.
    with monkeypatch.context() as locked:
        deletes = _locked(locked, "unlink", 2, record)
        patient(record.unlink)
    assert not record.exists() and len(deletes) == 3
    second = repo.forge("work", "BOARD/PAGE")
    assert second.returncode == 0, second.stdout + second.stderr
    assert _sent(calls, "turn/start")[-1]["input"][0]["text"].startswith("Fix round 2 on The page.\n")
