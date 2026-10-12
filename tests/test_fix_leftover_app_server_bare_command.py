"""A Codex app-server a crash left is stopped even when Forge read only its program's name."""
from __future__ import annotations

import os
import shutil
import sys

import pytest

from conftest import _install
from test_codex_record import BARE_SERVER, KILL, _codex_repo_direct, _down, _freeze, _held, _up
from test_codex_worker import sdk_data  # noqa: F401 (a fixture)

STORY = "pull-requests-keep-failing-ci-on-the-sam"


@pytest.mark.skipif(os.name == "nt", reason="Windows reads a process's image path, never a bare name")
def test_1_next_work_stops_a_leftover_app_server_recorded_by_its_bare_name(repo, monkeypatch,
                                                                           sdk_data, claude_session):
    folder, calls = _codex_repo_direct(repo, monkeypatch, sdk_data)
    record = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD" / "PAGE.json"
    # Under load, ps reads a just-started app-server's program name only, and Forge records that.
    _install(repo.bin, "ps", BARE_SERVER.format(python=sys.executable, ps=shutil.which("ps")))
    work, saved, stub = _held(repo, calls, record, "stall")
    assert "app-server" not in saved["app_server"]["command"]
    (repo.bin / "ps").unlink()

    # A crash that kills the driver, and forge work before it can act, leaves the app-server.
    _freeze(work.pid)
    os.kill(saved["driver"]["pid"], KILL)
    work.kill()
    work.communicate()
    assert _down(saved["driver"]["pid"]) and _up(stub)

    # The next forge work stops it by the id and start time on record, and runs.
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _down(stub)
