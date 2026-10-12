"""Close checks each test a worker names in its proof list against close's own test run."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import body, env  # noqa: F401

STORY = "forge-writes-proof-list"
PROOF = ("Proof list:\n- Returning readers are greeted: tests/test_greeting.py::test_returning\n"
         "- Empty names are refused: tests/test_greeting.py::test_empty")


def _close(env, adopted, command):
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    text = (repo.path / "forge.toml").read_text("utf-8").replace('version = "v1.2.2"',
                                                                  f'version = "{version}"')
    kept = [line for line in text.splitlines()
            if line.partition("=")[0].strip() not in ("test", "fast_test", "checks")]
    env.commit(repo.path, "forge.toml", f"test = {json.dumps(command)}\nchecks = [\"forge-pr-check\"]\n"
               + "\n".join(kept) + "\n", "Run the tests")
    repo.git("push", "-q", "origin", "main")
    # The worker names a test that exists and one that does not, and writes no results.
    item, where = env.start_fix({"tests/test_greeting.py": "def test_returning():\n    assert True\n"})
    repo.git("commit", "--allow-empty", "-q", "-m", "List the proof", "-m", PROOF, cwd=where)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    return " ".join(env.prompt().split()), body(env.gh_calls("pr", "create")[-1])


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_a_named_test_that_did_not_run_shows_as_not_run(env, adopted):
    python = Path(sys.executable).as_posix()
    prompt, published = _close(env, adopted, f'"{python}" -m pytest -q -p no:cacheprovider tests')
    assert "tests/test_greeting.py::test_empty: not run: no such test" in prompt
    assert "tests/test_greeting.py::test_returning: not run" not in prompt
    assert "tests/test_greeting.py::test_returning: passed in close's run" in published
    assert "tests/test_greeting.py::test_empty: not run" in published


def test_2_a_runner_without_test_names_shows_the_command_and_its_result(env):
    python = Path(sys.executable).as_posix()
    command = f'"{python}" -c "print(1)"'
    _, published = _close(env, False, command)
    assert (f"tests/test_greeting.py::test_returning: no single test results; "
            f"`{command}` exited with status 0") in published
    assert "tests/test_greeting.py::test_empty: not run: no such test" in published
