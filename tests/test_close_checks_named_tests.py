"""Close checks each test a worker names in its proof list against close's own test run."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401

STORY = "forge-writes-proof-list"
PROOF = ("Proof list:\n- Returning readers are greeted: tests/test_greeting.py::test_returning\n"
         "- Empty names are refused: tests/test_greeting.py::test_empty\n"
         "- Old readers stay greeted: tests/test_other.py::test_other\n"
         "- New readers by name: tests/test_greeting.py::test_case[new]\n"
         "- Readers coming back by name: tests/test_greeting.py::test_case[back]\n"
         "- The page greets readers: src/greet.test.ts\n"
         "- The page greets readers again: __tests__/greeting.js")
GREETING = ("import pytest\n\n\ndef test_returning():\n    assert True\n\n\n"
            "@pytest.mark.parametrize(\"who\", [\"new\", \"back\"])\ndef test_case(who):\n"
            "    assert who == \"new\"\n")


def _close(env, adopted, command, red=False):
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
    # The worker maps items to a test that runs, one that does not exist, one close does not run
    # and one in another language, and writes no results.
    item, where = env.start_fix({".gitignore": "__pycache__/\n", "tests/test_greeting.py": GREETING,
                                 "tests/test_other.py": "def test_other():\n    assert True\n",
                                 "src/greet.test.ts": "test('greets', () => {});\n"})
    repo.git("commit", "--allow-empty", "-q", "-m", "List the proof", "-m", PROOF, cwd=where)
    for _ in range(1 if red else 2):  # a second close reuses the passing run on the same files
        closed = env.close(item)
        assert (closed.returncode != 0) == red, closed.stdout + closed.stderr
    # The body as gh received it on the last publish, before any later rewrite of its file.
    sent = (env.repo.bin / "gh-bodies.jsonl").read_text("utf-8").splitlines()
    assert env.gh_calls("pr", "edit"), "close never refreshed the pull request after its run"
    return env.prompt(), json.loads(sent[-1])


@pytest.mark.parametrize("adopted, red", [(False, False), (True, False), (False, True)],
                         ids=["new-client", "earlier-adoption", "failed-test"])
def test_1_close_writes_the_proof_list_from_the_tests_it_ran(env, adopted, red):
    python = Path(sys.executable).as_posix()
    command = f'"{python}" -m pytest -q -p no:cacheprovider tests/test_greeting.py'
    prompt, published = _close(env, adopted, command if red else command + ' -k "not back"', red)
    assert ("- Returning readers are greeted: tests/test_greeting.py::test_returning "
            "(passed in close's run)") in published
    assert "- Empty names are refused: not run" in published
    assert "- Old readers stay greeted: not run" in published
    assert "test_empty" not in published and "test_other" not in published
    # A named case matches only itself; a case that failed shows as failed.
    assert "- New readers by name: tests/test_greeting.py::test_case[new] (passed in close's run)" in published
    assert ("- Readers coming back by name: tests/test_greeting.py::test_case[back] (failed in close's run)"
            if red else "- Readers coming back by name: not run") in published
    # A test close cannot match to its run's results is never copied as proof.
    assert "- The page greets readers: src/greet.test.ts (not checked)" in published
    assert "- The page greets readers again: __tests__/greeting.js (not checked)" in published
    # The review runs alongside the tests, so its list names only the tests the branch has.
    assert "- Empty names are refused: not run" in prompt
    assert "test_empty" not in prompt


def test_2_a_runner_without_test_results_shows_named_tests_as_not_checked(env):
    python = Path(sys.executable).as_posix()
    _, published = _close(env, False, f'"{python}" -c "print(1)"')
    assert ("- Returning readers are greeted: tests/test_greeting.py::test_returning (not checked)"
            in published)
    assert "test_empty" not in published
