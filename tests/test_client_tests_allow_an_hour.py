"""Client CI allows an hour through real init and earlier-adopted sync.

Audit: protects the Actions budget from the old thirty-minute default.
Existing tests assert the old limit. No new production seam is needed.
"""
import pytest

from test_groups_pytest import _adopted_client, _new_client
from test_testplace_workflow import _jobs

STORY = "FIX-CLIENT-TESTS-JOB-60-MINUTES"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_client_tests_allow_sixty_minutes_on_init_and_sync(repo, gh, tmp_path, adopted):
    client = (_adopted_client(repo, tmp_path, "hour-client") if adopted else
              _new_client(repo, gh, tmp_path, "hour-client"))
    jobs = _jobs((client / ".github/workflows/forge.yml").read_text(encoding="utf-8"))
    assert "    timeout-minutes: 60\n" in jobs["tests"]
    assert "    timeout-minutes: 60\n" in jobs["full-suite"]
