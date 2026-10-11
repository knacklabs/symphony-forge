"""Close picks local tests that name or import a changed file, so a test that runs the program
from outside is missed; close names each such file and workers search the tests for printed text."""
from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

from test_workers_leave_settings_to_coordinator import client  # noqa: F401
from test_worker import calls, install_claude

STORY = "test-gap-warning"


def test_1_close_names_each_changed_source_file_no_test_mentions(client, tmp_path):
    command = shlex.join([Path(sys.executable).as_posix(), "-m", "pytest", "tests", "-q"])
    config = (client.path / "forge.toml").read_text("utf-8")
    client.write("forge.toml", "test = " + json.dumps(command) + "\n" + "\n".join(
        line for line in config.splitlines() if not line.startswith("test =")) + "\n")
    client.write("src/app/named.py", "VALUE = 1\n")
    client.write("src/app/unnamed.py", "VALUE = 1\n")
    client.write("tests/test_named.py", "# app/named.py\ndef test_named():\n    assert True\n")
    client.git("add", "-A")
    client.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-q", "-m", "Set up tests")
    base = client.git("rev-parse", "HEAD").strip()
    client.write("src/app/named.py", "VALUE = 2\n")
    client.write("src/app/unnamed.py", "VALUE = 2\n")

    result = client.forge("test", "--pytest", base)

    assert result.returncode == 0, result.stdout + result.stderr
    # Last, so close's bounded output tail still shows it.
    assert result.stdout.splitlines()[-1] == (
        "No local test names src/app/unnamed.py; GitHub's checks will cover it.")
    assert "src/app/named.py;" not in result.stdout


def test_2_worker_brief_says_run_the_tests_that_check_changed_printed_text(client):
    log = install_claude(client)
    started = client.forge("fix", "start", "Check printed text guidance", "--done",
                           "Workers run tests for printed text")
    assert started.returncode == 0, started.stdout + started.stderr
    worked = client.forge("work", "check-printed-text-guidance")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[0]["brief"].split())
    assert ("When you change text the program prints (messages, pull request text, board lines), "
            "search the tests for that text and run those tests too.") in brief
