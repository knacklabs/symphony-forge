"""A broad worker selection leaves the full suite to CI, even for shared fixtures."""
import json
import re
import subprocess
import sys
import time

import pytest

from test_close import STORY_DOC, env  # noqa: F401
from test_close_always_tests import adopt_earlier

STORY = "FIX-BOUNDED-WORKER-TESTS"


@pytest.mark.parametrize("adopted,kind,fast", [
    (False, "shared", True), (True, "shared", True),
    (False, "shared", False), (False, "broad", True),
    (False, "unnamed", True), (False, "task", True),
], ids=["init-shared-picker", "adopted-shared-picker", "init-shared-default",
        "init-broad", "init-no-named-tests", "init-task-tests-column"])
def test_1_worker_runs_item_tests_when_shared_inputs_or_a_broad_selection_change(
        env, monkeypatch, adopted, kind, fast):
    # The real pytest fixture records executed tests; no fake chooses the selection.
    # Previously bare forge test ran all 12 files after a shared-fixture edit.
    if adopted:
        adopt_earlier(env)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "")
    log = env.tmp / "ran"
    log.mkdir()
    command = subprocess.list2cmdline([sys.executable, "-m", "pytest", "tests", "-q"])
    settings = re.sub(r"^test = .*\n", "", (env.repo.path / "forge.toml").read_text("utf-8"), flags=re.M)
    settings = "test = " + json.dumps(command) + "\n" + settings
    if fast:
        settings = 'fast_test = "forge test --pytest {base}"\n' + settings
    env.repo.write("forge.toml", settings)
    fixture = ("import pathlib, pytest\n@pytest.fixture(autouse=True)\n"
               "def receipt(request):\n"
               f"    (pathlib.Path({json.dumps(log.as_posix())}) / request.node.name).touch()\n")
    env.repo.write("conftest.py", fixture)
    for number in range(12):
        env.repo.write(f"tests/test_case_{number}.py", f"def test_case_{number}():\n    assert 2 + 2 == 4\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Set up real client suite")
    if adopted:
        env.repo.git("switch", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/adopt")
    env.repo.git("-c", "core.hooksPath=/dev/null", "push", "-q", "origin", "main")
    count = 5 if kind == "broad" else 0 if kind in ("unnamed", "task") else 1
    changes = {f"tests/test_case_{number}.py":
               f"def test_case_{number}():\n    assert 3 + 3 == 6\n" for number in range(count)}
    if kind != "broad":
        changes["conftest.py"] = fixture + "# shared fixture changed\n"
    if kind == "task":
        doc = STORY_DOC.replace("`tests/test_app.py`", "`tests/test_case_7.py::test_case_7`")
        _, where = env.start_task(changes={"plans/SHOP.md": doc, **changes})
        expected = {"test_case_7"}
    else:
        _, where = env.start_fix(changes)
        expected = {f"test_case_{number}" for number in range(count)}
    started = time.monotonic()
    result = env.repo.forge("test", cwd=where)
    ran = {path.name for path in log.iterdir()}
    print(f"worker shared/broad case: {len(ran)}/12 tests in {time.monotonic() - started:.2f}s")
    assert result.returncode == 0, result.stdout + result.stderr
    assert ran == expected, result.stdout + result.stderr
    assert result.stdout.count("CI runs the full suite.") == 1, result.stdout
    # Explicit picker calls retain the full shared-input fallback.
    if kind == "shared" and not adopted and fast:
        base = env.repo.git("rev-parse", "origin/main", cwd=where)
        explicit = env.repo.forge("test", "--pytest", base, cwd=where)
        assert explicit.returncode == 0, explicit.stdout + explicit.stderr
        assert len(list(log.iterdir())) == 12
