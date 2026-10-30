"""The board reports the live review rather than an earlier saved result."""
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import CLEAN, env  # noqa: F401
from test_machine_views import view
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_mod_sync import _calls, _claude
from test_run_records import configure

STORY = "FIX-PANE-READABLE"
REVIEWING = json.loads((ROOT / "tests/fixtures/board.json").read_text("utf-8"))["reviewing"]


@pytest.mark.parametrize("previous", [False, True])
def test_1_running_review_has_a_positive_round_and_running_gate(env, previous):
    # Existing board tests manufacture run events. This regression lets close record
    # its actual first review, before any worker turn, and a review replacing findings.
    repo = configure(env)
    item, _ = env.start_fix(round=2 if previous else 0, steps=[],
                                 **({"review": {"findings": [{"title": "Input is lost", "priority": "P1",
                                                           "file": "app.py", "line": 1, "body": "Input is lost"}],
                                                "commit": repo.git("rev-parse", "HEAD")}}
                                    if previous else {}))
    env.reviews(CLEAN)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(60)
    helper = Path(os.environ["AUTOREVIEW"])
    source = helper.read_text("utf-8")
    helper.write_text(source.replace("args = sys.argv[1:]",
        "import socket\n"
        f"with socket.create_connection({listener.getsockname()!r}, timeout=60) as gate:\n"
        "    gate.recv(1)\nargs = sys.argv[1:]"), "utf-8")
    process = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "close", item],
        cwd=repo.path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        try:
            connection, _ = listener.accept()
        except TimeoutError:
            output, error = process.communicate(timeout=5)
            pytest.fail("Close did not reach its reviewer: " + output + error)
        row = next(row for row in view(repo, "board")["items"] if row["id"] == item)
        assert row["round"] == (2 if previous else REVIEWING["round"]), row
        assert row["worker"]["round"] == row["round"], row
        assert row["gates"]["review"] == REVIEWING["gates"]["review"], row
        assert next(stage for stage in row["stages"] if stage["name"] == "Review")["status"] == "running"
    finally:
        if "connection" in locals():
            connection.sendall(b"1")
            connection.close()
        listener.close()
        try:
            output, error = process.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise
    assert process.returncode == 0, output + error


@pytest.mark.parametrize("history", ["new", "existing"])
def test_2_init_delivers_the_board_plugin(repo, gh, tmp_path, history):
    # A successful scaffold alone leaves a fresh machine without the Board pane.
    client = _new_repo(repo, gh, tmp_path)
    args = []
    if history == "existing":
        (client / "README.md").write_text("Read the guide.\n", "utf-8")
        repo.git("add", "README.md", cwd=client)
        repo.git("commit", "-qm", "Start the project", cwd=client)
        repo.git("push", "-q", "-u", "origin", "main", cwd=client)
        repo.git("remote", "set-head", "origin", "main", cwd=client)
        args = ["--test", f'"{sys.executable}" -c "print(123)"', "--checks", "tests",
                "--interfaces", "src/routes/**", "--approver", "The owner", "--merger", "The owner"]
    _claude(repo)
    done = repo.forge("init", "--actions", "yes", *args, cwd=client)
    assert done.returncode == 0, done.stdout + done.stderr
    assert ["plugin", "install", "forge@forge", "--scope", "user"] in _calls(repo), done.stdout
