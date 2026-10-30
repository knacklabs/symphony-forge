"""Task test notes select runnable paths, never prose or Markdown annotations."""
import json
import re
import subprocess
import sys

import pytest

from test_close import STORY_DOC, env  # noqa: F401
from test_close_always_tests import adopt_earlier

STORY = "FIX-TASK-TEST-NOTES"


@pytest.mark.parametrize("adopted,notes,expected,keyword", [
    (False, "Run `tests/test_case_1.py` (`test_first`, `test_second`, new), then tests/test_case_2.py (existing).",
     {"test_first_1", "test_second_1", "test_first_2", "test_second_2"}, ""),
    (True, "tests/test_case_1.py::test_first_1 (new), tests/test_case_2.py::test_second_2 (existing)",
     {"test_first_1", "test_second_2"}, ""),
    (False, "tests/test_case_1.py::test_first_1, ::test_second_1 (new)",
     {"test_second_1"}, "second"),
    (False, "Check the HTTP cases, including the member export.", set(), ""),
], ids=["markdown-notes", "adopted-nodes", "abbreviated-filtered-nodes", "prose-only"])
def test_1_task_test_notes_run_named_tests_without_settings_errors(
        env, monkeypatch, adopted, notes, expected, keyword):
    # Existing bounded-worker coverage uses only a plain node. Real pytest receipts
    # expose notes becoming paths without a new production seam or fake selection.
    if adopted:
        adopt_earlier(env)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "")
    log = env.tmp / "ran"
    log.mkdir()
    command = subprocess.list2cmdline([sys.executable, "-m", "pytest", "tests", "-q"])
    settings = re.sub(r"^test = .*\n", "", (env.repo.path / "forge.toml").read_text("utf-8"), flags=re.M)
    env.repo.write("forge.toml", 'fast_test = "forge test --pytest {base}"\n'
                   + "test = " + json.dumps(command) + "\n" + settings)
    fixture = ("import pathlib, pytest\n@pytest.fixture(autouse=True)\n"
               "def receipt(request):\n"
               f"    (pathlib.Path({json.dumps(log.as_posix())}) / request.node.name).touch()\n")
    env.repo.write("conftest.py", fixture)
    for number in range(8):
        env.repo.write(f"tests/test_case_{number}.py",
                       f"def test_first_{number}():\n    assert 2 + 2 == 4\n"
                       f"def test_second_{number}():\n    assert 3 + 3 == 6\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Set up real client tests")
    if adopted:
        env.repo.git("switch", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/adopt")
    env.repo.git("-c", "core.hooksPath=/dev/null", "push", "-q", "origin", "main")
    doc = STORY_DOC.replace("`tests/test_app.py`", notes)
    _, where = env.start_task(changes={"plans/SHOP.md": doc,
                                      "conftest.py": fixture + "# shared change\n"})
    if keyword:
        monkeypatch.setenv("PYTEST_ADDOPTS", "-k " + keyword)
    result = env.repo.forge("test", cwd=where)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert {path.name for path in log.iterdir()} == expected, output
    assert "always_test names" not in output
    assert "Broad selection:" in output
