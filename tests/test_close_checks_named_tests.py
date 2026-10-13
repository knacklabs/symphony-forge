"""Close checks each test a worker names in its proof list against close's own test run."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401

STORY = "forge-writes-proof-list"
PROOF = ("Proof list:\n- Returning readers are greeted: tests/test_greeting.py::test_returning "
         "(including empty names)\n"
         "- Staff can sign in: tests/test_greeting.py::test_role[staff,active]\n"
         "- Later readers wait: tests/test_greeting.py::test_later\n"
         "- Empty names are refused: tests/test_greeting.py::test_empty\n"
         "- Old readers stay greeted: tests/test_other.py::test_other\n"
         "- New readers by name: tests/test_greeting.py::test_case[new]\n"
         "- Readers coming back by name: tests/test_greeting.py::test_case[back]\n"
         "- The page greets readers: src/greet.test.ts\n"
         "- The page greets readers again: __tests__/greeting.js\n"
         "- Every greeting: tests/test_greeting.py\n"
         "- Code spans name tests: `tests/test_greeting.py::test_returning`\n"
         "- Cleanup runs: tests/test_greeting.py::test_cleanup\n"
         "- Readers by name: tests/test_greeting.py::test_case")
# A test whose call passes and whose teardown fails.
TEARDOWN = ("\n\n@pytest.fixture\ndef broken():\n    yield\n    raise RuntimeError(\"teardown\")\n\n\n"
            "def test_cleanup(broken):\n    pass\n")
GREETING = ("import pytest\n\n\ndef test_returning():\n    assert True\n\n\n"
            "@pytest.mark.parametrize(\"who\", [\"new\", \"back\"])\ndef test_case(who):\n"
            "    assert who == \"new\"\n\n\n"
            "@pytest.mark.parametrize(\"role\", [\"staff\"], ids=[\"staff,active\"])\n"
            "def test_role(role):\n    assert role\n\n\n"
            "@pytest.mark.skip(reason=\"later\")\ndef test_later():\n    pass\n")


def _close(env, adopted, command, red=False, greeting=GREETING, docs_only=False):
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
    # The worker maps items to a test that runs, one that does not exist, one close does not run
    # and one in another language, and writes no results.
    files = {".gitignore": "__pycache__/\n", "tests/test_greeting.py": greeting,
             "tests/test_other.py": "def test_other():\n    assert True\n",
             "src/greet.test.ts": "test('greets', () => {});\n"}
    if docs_only:  # the tests are already on the default branch; the fix changes only a readme
        for path, text in files.items():
            env.commit(repo.path, path, text, "Add the tests")
        files = {"README.md": "Hello, readers.\n"}
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix(files)
    repo.git("commit", "--allow-empty", "-q", "-m", "List the proof", "-m", PROOF, cwd=where)
    for _ in range(1 if red else 2):  # a second close reuses the passing run on the same files
        closed = env.close(item)
        assert (closed.returncode != 0) == red, closed.stdout + closed.stderr
    # The body as gh received it on the last publish, before any later rewrite of its file.
    sent = (env.repo.bin / "gh-bodies.jsonl").read_text("utf-8").splitlines()
    assert env.gh_calls("pr", "edit"), "close never refreshed the pull request after its run"
    return env.prompt(), json.loads(sent[-1])


@pytest.mark.parametrize("adopted, red, options, teardown", [
    (False, False, "", False), (True, False, "", False), (False, True, "", False),
    (False, False, " -ra", False), (False, False, " && {run} tests/test_other.py", False),
    (False, True, "", True)], ids=["new-client", "earlier-adoption", "failed-test",
                                   "own-report-options", "two-pytest-runs", "teardown-error"])
def test_1_close_writes_the_proof_list_from_the_tests_it_ran(env, adopted, red, options, teardown):
    run = f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider'
    # The client's own report options, such as -ra, cannot hide close's per-test results, and a
    # second pytest in the command keeps the first one's results.
    command = f'{run} tests/test_greeting.py' + ("" if red else ' -k "not back"')
    prompt, published = _close(env, adopted, command + options.format(run=run), red,
                               GREETING + TEARDOWN if teardown else GREETING)
    # A name in a code span matches without its backtick.
    assert "`tests/test_greeting.py::test_returning (passed in close's run)`" in published
    # A test has one result, the worst of its phases: a failed teardown is an error.
    assert ("- Cleanup runs: tests/test_greeting.py::test_cleanup (error in close's run)"
            if teardown else "- Cleanup runs: not run") in published
    # Close keeps the worker's words and adds each named test's result next to it.
    assert ("- Returning readers are greeted: tests/test_greeting.py::test_returning "
            "(passed in close's run) (including empty names)") in published
    # A parameter id runs to its closing bracket, commas and all.
    assert ("- Staff can sign in: tests/test_greeting.py::test_role[staff,active] "
            "(passed in close's run)") in published
    assert "- Empty names are refused: not run" in published
    assert ("- Old readers stay greeted: tests/test_other.py::test_other (passed in close's run)"
            if "test_other" in options else "- Old readers stay greeted: not run") in published
    assert "test_empty" not in published
    # A name that matches several cases counts the cases that ran.
    assert ("- Every greeting: tests/test_greeting.py (3 passed, 1 failed, 1 error, 1 skipped in close's run)"
            if teardown else
            "- Every greeting: tests/test_greeting.py (3 passed, 1 failed, 1 skipped in close's run)"
            if red else "- Every greeting: tests/test_greeting.py (3 passed, 1 skipped in close's run)"
            ) in published
    # A test name without its parameter id counts the cases that ran.
    assert ("- Readers by name: tests/test_greeting.py::test_case (1 passed, 1 failed in close's run)"
            if red else "- Readers by name: tests/test_greeting.py::test_case (1 passed in close's run)"
            ) in published
    # A named case matches only itself; a case that failed shows as failed.
    assert "- New readers by name: tests/test_greeting.py::test_case[new] (passed in close's run)" in published
    assert ("- Readers coming back by name: tests/test_greeting.py::test_case[back] (failed in close's run)"
            if red else "- Readers coming back by name: not run") in published
    assert "- Later readers wait: tests/test_greeting.py::test_later (skipped in close's run)" in published
    # A test close cannot match to its run's results is never copied as proof.
    assert "- The page greets readers: src/greet.test.ts (not checked)" in published
    assert "- The page greets readers again: __tests__/greeting.js (not checked)" in published
    # The review runs alongside the tests, so its list names only the tests the branch has.
    assert "- Empty names are refused: not run" in prompt
    assert "test_empty" not in prompt


def test_2_a_runner_without_test_results_shows_named_tests_as_not_checked(env):
    python = Path(sys.executable).as_posix()
    _, published = _close(env, False, f'"{python}" -c "print(1)"')
    assert ("- Returning readers are greeted: tests/test_greeting.py::test_returning (not checked) "
            "(including empty names)") in published
    assert "test_empty" not in published


def test_3_a_change_close_runs_no_tests_for_shows_named_tests_as_not_run(env):
    python = Path(sys.executable).as_posix()
    _, published = _close(env, False, f'"{python}" -m pytest -q -p no:cacheprovider tests',
                          docs_only=True)
    assert ("- Returning readers are greeted: not run (close ran no tests for this change) "
            "(including empty names)") in published
    assert "test_returning" not in published
