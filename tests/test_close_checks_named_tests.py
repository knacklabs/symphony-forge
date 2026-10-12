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
         "- Empty names are refused: tests/test_greeting.py::test_empty\n"
         "- Old readers stay greeted: tests/test_other.py::test_other")


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
    # The worker maps items to a test that runs, one that does not exist and one close does not
    # run, and writes no results.
    item, where = env.start_fix({"tests/test_greeting.py": "def test_returning():\n    assert True\n",
                                 "tests/test_other.py": "def test_other():\n    assert True\n"})
    repo.git("commit", "--allow-empty", "-q", "-m", "List the proof", "-m", PROOF, cwd=where)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    return env.prompt(), body(env.gh_calls("pr", "create")[-1])


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_close_writes_the_proof_list_from_the_tests_it_ran(env, adopted):
    python = Path(sys.executable).as_posix()
    prompt, published = _close(env, adopted,
                               f'"{python}" -m pytest -q -p no:cacheprovider tests/test_greeting.py')
    assert ("- Returning readers are greeted: tests/test_greeting.py::test_returning "
            "(passed in close's run)") in published
    assert "- Empty names are refused: not run" in published
    assert "- Old readers stay greeted: not run" in published
    assert "test_empty" not in published and "test_other" not in published
    # The review runs alongside the tests, so its list names only the tests the branch has.
    assert "- Empty names are refused: not run" in prompt
    assert "test_empty" not in prompt


def test_2_a_runner_without_test_names_shows_the_command_and_its_result(env):
    python = Path(sys.executable).as_posix()
    command = f'"{python}" -c "print(1)"'
    _, published = _close(env, False, command)
    assert f"- Returning readers are greeted: `{command}` exited with status 0" in published
    assert "test_returning" not in published and "test_empty" not in published
