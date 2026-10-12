"""Close picks local tests that name or import a changed file, so a test that runs the program
from outside is missed; close names each such file and workers search the tests for printed text."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import tomllib

import pytest

from test_close import env, run  # noqa: F401 (pytest fixture)
from test_workers_leave_settings_to_coordinator import client  # noqa: F401
from test_worker import calls, install_claude

STORY = "test-gap-warning"


@pytest.mark.parametrize("others", [3, 0], ids=["runs-selected", "skips-large-selection"])
def test_1_close_names_each_changed_source_file_no_test_mentions(env, monkeypatch, others):
    # Forge's own settings and dependencies; only review and GitHub are faked. A second
    # runner prints after pytest, as Jest does after the Python part of a mixed command.
    for rel in ("forge.toml", "pyproject.toml", "uv.lock"):
        env.repo.write(rel, (ROOT / rel).read_text("utf-8"))
    settings = tomllib.loads((ROOT / "forge.toml").read_text("utf-8"))
    later = f'"{Path(sys.executable).as_posix()}" -c "for i in range(40): print(i)"'  # sh and cmd
    env.repo.write("forge.toml", (ROOT / "forge.toml").read_text("utf-8").replace(
        json.dumps(settings["fast_test"]), json.dumps(settings["fast_test"] + " && " + later)))
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", sys.prefix)
    monkeypatch.setenv("UV_NO_SYNC", "1")  # Reuse the enclosing run's installed test dependencies.
    for name in ("named", "first", "second"):
        env.repo.write(f"src/app/{name}.py", "VALUE = 1\n")
    env.repo.write("tests/test_named.py", "# app/named.py\ndef test_named():\n    assert True\n")
    for number in range(others):  # Close skips local tests when over a third would run.
        env.repo.write(f"tests/test_other_{number}.py", "def test_other():\n    assert True\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Use Forge's own test settings")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix({f"src/app/{name}.py": "VALUE = 2\n"
                             for name in ("named", "first", "second")})
    env.checks([run(name) for name in settings["checks"]])

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    for name in ("first", "second"):
        assert (f"No local test names src/app/{name}.py; GitHub's checks will cover it."
                in closed.stdout), closed.stdout
    assert "No local test names src/app/named.py" not in closed.stdout


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
