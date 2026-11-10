"""A dead parallel worker must not hide the test run's failures.

Test-audit: protect command output after a real worker exits without its report.
The unguarded workeroutput access crashes before pytest finishes reporting.
Existing parallel retry tests let workers finish normally and miss this lifecycle.
Real pytest and xdist run through forge test, with no production test seam.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT

STORY = "when-a-parallel-test-process-dies-during"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_parallel_worker_crash_keeps_failed_test_names(repo, gh, monkeypatch, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    command = (f'"{Path(sys.executable).as_posix()}" -m pytest tests -q '
               '-n 1 --max-worker-restart=0')
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
               'checks = ["tests"]\n' + f'test = {json.dumps(command)}\n')
    repo.write("tests/test_result.py", "import os\n"
               "def test_failure():\n    assert False, 'real assertion failure'\n"
               "def test_worker_dies():\n    os._exit(42)\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure parallel tests")
    repo.git("push", "-q", "origin", "main")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)

    run = repo.forge("test", "--full")

    output = run.stdout + run.stderr
    assert "INTERNALERROR" not in output, output
    assert run.returncode != 0, output
    failures = output.split("Failed tests:\n", 1)[-1]
    assert "- tests/test_result.py::test_failure\n" in failures, output
    assert "- tests/test_result.py::test_worker_dies\n" in failures, output
