"""On macOS a dead Codex driver leaves no app-server behind it."""
from __future__ import annotations

import os
import shutil
import sys

from conftest import _install
from test_codex_record import BARE_SERVER, KILL, _codex_repo_direct, _held, _up
from test_codex_worker import sdk_data  # noqa: F401 (a fixture)

STORY = "MACOS-APP-SERVER"


def test_12_a_dead_driver_leaves_no_app_server_behind(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo_direct(repo, monkeypatch, sdk_data)
    record = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD" / "PAGE.json"
    if os.name != "nt":
        # Forge reads only "python" as the app-server's command, so it can't tell it by that.
        _install(repo.bin, "ps", BARE_SERVER.format(python=sys.executable, ps=shutil.which("ps")))
    work, saved, stub = _held(repo, calls, record, "hold")
    if os.name != "nt":
        assert "app-server" not in saved["app_server"]["command"]
    os.kill(saved["driver"]["pid"], KILL)
    assert "Codex never reported its end" in work.communicate(timeout=30)[1]
    assert not _up(stub)  # already gone when forge work returns, not a moment later
