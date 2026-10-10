"""Close tests remain tests after the completed worker releases its build lock.

Audit: the saved working status plus a live test used to say a worker was building.
Existing nested worker/test coverage keeps the worker alive, so misses this lifecycle.
Real work, close, board and next own the result; only model/GitHub edges are faked.
"""
import json
import re

import pytest

from test_board_dependency_timelines import _client
from test_board_status_and_times import _board, _row
from test_close import GREEN, env  # noqa: F401
from test_lanes_agents import start
from test_lanes_tests import accepted, configure, reap, release_server  # noqa: F401
from test_story import worktree
from test_worker import install_claude

STORY = "FIX-BOARD-DATA-TRUTH"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_13_close_tests_after_worker_exit_show_tests_running(
        env, tmp_path, monkeypatch, release_server, history):
    repo = env.repo
    settings = (repo.path / "forge.toml").read_text("utf-8")
    _client(repo, env.gh, tmp_path, history)
    # Client setup has already landed; this case tests reporting, not commit gates.
    repo.git("config", "core.hooksPath", (tmp_path / "fixture-hooks").as_posix())
    env.commit(repo.path, "forge.toml", settings)
    server, connections = release_server
    configure(env, server)
    env.checks(GREEN)
    install_claude(repo)
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "product.txt")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "1")
    item = "show-close-tests"
    made = repo.forge("fix", "start", "Show close tests", "--done", "Readers see test activity",
                      "--slug", item)
    assert made.returncode == 0, made.stdout + made.stderr
    folder = worktree(repo, "fix/" + item)
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert json.loads((folder / f".factory/fixes/{item}.json").read_text("utf-8"))["status"] == "working"
    processes = []
    try:
        closing, output = start(repo.path, tmp_path / "closing", repo, "close", item)
        processes.append(closing)
        connection, _ = accepted(server, connections, folder, closing, output)
        data, text, _ = _board(repo, tmp_path)
        row = _row(data, item)
        assert row["worker"] is None
        assert row["tests"] is not None
        assert next(stage for stage in row["stages"] if stage["name"] == "Tests")["status"] == "running"
        assert re.search(r"tests?.*running|running.*tests?", row["status"], re.I), row["status"]
        assert re.search(r"tests?.*running|running.*tests?", text, re.I), text
        shown = repo.forge("next")
        assert shown.returncode == 0, shown.stdout + shown.stderr
        assert "A worker is building" not in shown.stdout
        assert re.search(r"tests?.*running|running.*tests?", shown.stdout, re.I), shown.stdout
        connection.sendall(b"x")
        assert closing.wait(timeout=120) == 0, output.read_text("utf-8")
    finally:
        reap(processes, server, connections)
