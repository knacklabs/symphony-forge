"""Short task names run tests; only unmatched named selections fail."""
import subprocess
import sys

import pytest

from test_close import env  # noqa: F401
from test_task_test_notes_select_tests import run_task
from test_fast_test_honors_pytest_inputs import run_picker

STORY = "FIX-SHORT-TEST-NAMES"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_short_names_run_matching_tests(env, monkeypatch, adopted):
    # Reuse the real command fixture and its receipts, with a descriptive suffix.
    run_task(env, monkeypatch, adopted,
             "tests/test_case_1.py::test_2", {"test_2_descriptive_name"}, "",
             extra="def test_2_descriptive_name():\n    assert True\n"
                   "def test_20_other_rule():\n    assert False\n"
                   "def test_2other():\n    assert False\n")


def test_2_empty_selections_fail_plainly(env, monkeypatch):
    run_task(env, monkeypatch, False, "tests/test_case_1.py::test_missing", set(), "", empty=True)


def test_3_no_related_tests_passes_with_a_plain_message(repo, monkeypatch):
    # The ordinary picker has no task selection and no tests related to this source.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "")
    repo.write("tests/test_unrelated.py", "def test_unrelated():\n    assert False\n")
    command = subprocess.list2cmdline([sys.executable, "-m", "pytest", "tests", "-q"])
    result = run_picker(repo, command)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "No tests ran: no changed or module-related test files were selected." in output
