"""A failed close ends its test report with every failure and the full log path."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401

STORY = "FIX-CLOSE-LISTS-EVERY-FAILED-TEST"


# Audit: the real close must preserve failures beyond its output tail. Existing close
# tests check red status or proof entries, not the complete failure list or log access.
# Real pytest decides the failures; no production seam or fake test runner is needed.
@pytest.mark.parametrize("adopted,collection", [(False, False), (True, False), (False, True)],
                         ids=["new-client", "earlier-adoption", "collection-error"])
def test_1_failed_close_ends_with_all_failed_test_files_names_and_full_log(env, adopted, collection):
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    config = (repo.path / "forge.toml").read_text("utf-8").replace(
        'version = "v1.2.2"', f'version = "{version}"')
    kept = [line for line in config.splitlines()
            if line.partition("=")[0].strip() not in ("test", "fast_test")]
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q -ra --tb=no -p no:cacheprovider'
    env.commit(repo.path, "forge.toml", f"test = {json.dumps(command)}\n"
               f"fast_test = {json.dumps(command)}\n" + "\n".join(kept) + "\n")
    repo.git("push", "-q", "origin", "main")
    names = (["tests/test_broken.py"] if collection else
             [f"tests/test_failures.py::test_case[{n}]" for n in range(45)]
             + ["tests/test_cleanup.py::test_cleanup", "tests/test_cleanup.py::test_setup"])
    files = {"tests/conftest.py":
             "def pytest_terminal_summary(terminalreporter):\n"
             "    for n in range(100):\n"
             "        terminalreporter.write_line('diagnostic detail ' + str(n))\n"}
    if collection:
        files["tests/test_broken.py"] = "raise RuntimeError('collection broke')\n"
    else:
        files["tests/test_failures.py"] = (
            "import pytest\n@pytest.mark.parametrize('n', range(45))\n"
            "def test_case(n):\n    assert n < 0\n")
        files["tests/test_cleanup.py"] = (
            "import pytest\n@pytest.fixture\ndef cleanup():\n    yield\n"
            "    raise RuntimeError('cleanup broke')\ndef test_cleanup(cleanup):\n    pass\n"
            "@pytest.fixture\ndef setup():\n    raise RuntimeError('setup broke')\n"
            "def test_setup(setup):\n    pass\n")
    item, _ = env.start_fix(files)
    closed = env.close(item)
    assert closed.returncode != 0, closed.stdout + closed.stderr
    footer = closed.stdout.rsplit("Failed tests:\n", 1)[-1]
    assert footer.splitlines()[:-1] == [f"- {name}" for name in sorted(names)], closed.stdout
    assert footer.splitlines()[-1].startswith("Full test log: "), footer
    log = Path(footer.splitlines()[-1].removeprefix("Full test log: "))
    assert log.is_file(), log
    output = log.read_text("utf-8")
    assert "diagnostic detail 0" in output and "diagnostic detail 99" in output
    for name in names:
        assert name in output
