"""The test helpers that read and write a record under a test's temp folder wait out the moment
Windows keeps a file from them, and fail only once it stays locked for five seconds."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from test_codex_record import _save, _saved

STORY = "windows-ci-jobs-keep-failing-with-permis"


def _locked(monkeypatch, method: str, times: float) -> list[int]:
    """Make Path.<method> refuse as a locked file does on Windows, this many times."""
    real, calls = getattr(Path, method), []

    def refuse(self, *args, **kwargs):
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
