"""forge.toml's always_test: close's pytest picker runs those tests beside the ones it picks."""
import json
import re
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT
from test_close import env, run  # noqa: F401

STORY = "close-always-tests"


def adopt_earlier(env):
    # An existing client repo, adopted on an earlier release and synced to this one.
    version = env.repo.forge("--version").stdout.split()[-1]
    env.repo.git("switch", "-qc", "fix/adopt")
    env.repo.write(".factory/fixes/adopt.json", json.dumps({
        "kind": "fix", "branch": "fix/adopt", "why": "Adopt", "done_when": "Adopted",
        "status": "started"}))
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", env.repo.path, dirs_exist_ok=True)
    settings = (env.repo.path / "forge.toml").read_text("utf-8")
    env.repo.write("forge.toml", settings.replace('version = "v1.2.2"', f'version = "{version}"'))
    synced = env.repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Refresh earlier adoption")


def set_up(env, monkeypatch, adopted, always, changed=1, options=()):
    if adopted:
        adopt_earlier(env)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "")
    log = env.tmp / "ran"
    log.mkdir()
    # The test command names only tests/unit; an always_test entry may sit outside it.
    command = subprocess.list2cmdline([sys.executable, "-m", "pytest", "tests/unit", "-q", *options])
    settings = re.sub(r"^test = .*\n", "", (env.repo.path / "forge.toml").read_text("utf-8"), flags=re.M)
    settings = "test = " + json.dumps(command) + "\n" + settings
    listed = ("always_test = " + (always if isinstance(always, str) else json.dumps(always)) + "\n"
              if always is not None else "# no always_test\n")
    # changed=0: the fix changes only forge.toml, adding always_test there.
    env.repo.write("forge.toml", settings if changed == 0 else listed + settings)
    env.repo.write("conftest.py", "import pathlib, pytest\n"
                   "@pytest.fixture(autouse=True)\ndef receipt(request):\n"
                   f"    (pathlib.Path({json.dumps(log.as_posix())}) / request.node.name).touch()\n")
    for number in range(8):
        env.repo.write(f"tests/unit/test_case_{number}.py",
                       f"def test_case_{number}():\n    assert True\n"
                       f"def test_other_{number}():\n    assert True\n")
    env.repo.write("tests/contracts/test_rules.py", "def test_rule():\n    assert True\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Set up real test suite")
    if adopted:  # stands in for the merged pull request that the synced hooks require
        env.repo.git("switch", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/adopt")
    env.repo.git("-c", "core.hooksPath=/dev/null", "push", "-q", "origin", "main")
    item, _ = env.start_fix({f"tests/unit/test_case_{number}.py": f"def test_case_{number}():\n    assert 2 + 2 == 4\n"
                             for number in range(changed)} or {"forge.toml": listed + settings})
    env.checks([run("tests"), run("forge-pr-check")])
    return item, log


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption"])
@pytest.mark.parametrize("always", [None, ["tests/unit/test_case_5.py", "tests/unit/test_case_6.py::test_other_6",
                                            "tests/contracts/test_rules.py"]],
                         ids=["unset", "set"])
@pytest.mark.parametrize("changed", [1, 4, 0], ids=["small", "large", "settings-only"])
def test_1_close_runs_always_test_beside_the_picked_tests(env, monkeypatch, adopted, always, changed):
    # A large or settings-only change skips the picked tests, but the listed ones still run.
    item, log = set_up(env, monkeypatch, adopted, always, changed)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    expected = ({"test_case_0"} if changed == 1 else set()) | (
        {"test_case_5", "test_other_5", "test_other_6", "test_rule"} if always else set())
    assert {path.name for path in log.iterdir()} == expected
    assert ("More than a third of the test files selected" in closed.stdout) == (changed > 1)


@pytest.mark.parametrize("value, options, problem", [
    ('"tests/test_rules.py"', (), "always_test must be a list of strings"),
    ('["tests/test_missing.py::test_1"]', (), "tests/test_missing.py::test_1"),
    ('["--help"]', (), "always_test lists --help, which is not a test path or node ID; list only tests"),
    ('["tests/unit/test_case_6.py::test_typo"]', (),
     "always_test names tests/unit/test_case_6.py::test_typo, which ran no test"),
    # The test command's -k deselects the listed test after collection.
    ('["tests/unit/test_case_6.py::test_other_6"]', ("-k", "not test_other_6"),
     "always_test names tests/unit/test_case_6.py::test_other_6, which ran no test"),
])
def test_2_close_refuses_an_always_test_it_cannot_run(env, monkeypatch, value, options, problem):
    item, _ = set_up(env, monkeypatch, False, value, options=options)
    closed = env.close(item)
    assert closed.returncode != 0
    assert problem in closed.stdout + closed.stderr


def test_3_the_guides_name_always_test():
    for rel in ("src/forge/templates/skill.md", ".claude/skills/forge/SKILL.md", ".codex/skills/forge/SKILL.md"):
        text = " ".join((ROOT / rel).read_text("utf-8").split())
        assert ("List them in `always_test` in `forge.toml` (in a fix), as test files or pytest node IDs"
                in text and "close runs them on every change" in text), rel
