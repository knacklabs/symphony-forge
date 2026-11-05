"""Short task names run descriptive tests and empty selections fail plainly."""
import pytest

from test_close import env  # noqa: F401
from test_task_test_notes_select_tests import run_task

STORY = "FIX-SHORT-TEST-NAMES"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_short_names_run_matching_tests(env, monkeypatch, adopted):
    # Reuse the real command fixture and its receipts, with a descriptive suffix.
    run_task(env, monkeypatch, adopted,
             "tests/test_case_1.py::test_2", {"test_2_descriptive_name"}, "",
             extra="def test_2_descriptive_name():\n    assert True\n"
                   "def test_20_other_rule():\n    assert False\n"
                   "def test_2other():\n    assert False\n")


@pytest.mark.parametrize("notes", ["tests/test_case_1.py::test_missing", "Check the HTTP cases."])
def test_2_empty_selections_fail_plainly(env, monkeypatch, notes):
    run_task(env, monkeypatch, False, notes, set(), "", empty=True)
