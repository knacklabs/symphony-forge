"""A dead Codex driver leaves no app-server behind it."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from conftest import _install
from test_codex_record import BARE_SERVER, KILL, _codex_repo_direct, _held, _up
from test_codex_worker import sdk_data  # noqa: F401 (a fixture)

STORY = "tests-test-macos-app-server-py-test-12-a"


def test_1_dead_driver_leaves_no_app_server_behind(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo_direct(repo, monkeypatch, sdk_data)
    record = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD" / "PAGE.json"
    if os.name != "nt":
        # Forge reads only "python" as the app-server's command, so it can't tell it by that.
        _install(repo.bin, "ps", BARE_SERVER.format(python=sys.executable, ps=shutil.which("ps")))
    read_text = Path.read_text
    denied = False

    def temporarily_unreadable(path, *args, **kwargs):
        nonlocal denied
        if path == record and path.exists() and not denied:
            denied = True
            raise PermissionError(13, "The record is temporarily in use", str(path))
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", temporarily_unreadable)
    work, saved, stub = _held(repo, calls, record, "hold")
    assert denied
    if os.name != "nt":
        assert "app-server" not in saved["app_server"]["command"]
    os.kill(saved["driver"]["pid"], KILL)
    assert "Codex never reported its end" in work.communicate(timeout=30)[1]
    assert not _up(stub)  # already gone when forge work returns, not a moment later
