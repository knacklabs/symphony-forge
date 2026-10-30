"""Full runs get an hour while pull request tests keep thirty minutes.

Test-audit gate:
1. Protect the generated Actions job limits through real init and sync commands.
2. Reusing the pull request limit cancels full-suite groups before they finish.
3. Existing nightly coverage requires equal limits; this owns the new separate limits.
4. Reuse client fixtures and inspect the workflow GitHub consumes. No new seam.
"""
import pytest

from test_groups_pytest import _adopted_client, _new_client, _settings
from test_testplace_workflow import _jobs

STORY = "FIX-THE-GROUPED-FULL-RUN-USES-THE-PULL-REQUE"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_full_runs_get_sixty_minutes_and_pr_tests_keep_thirty(repo, gh, tmp_path, adopted):
    client = (_adopted_client(repo, tmp_path, "budget-client") if adopted else
              _new_client(repo, gh, tmp_path, "budget-client"))
    if not adopted:
        initial = _jobs((client / ".github/workflows/forge.yml").read_text(encoding="utf-8"))
        assert "    timeout-minutes: 60\n" in initial["full-suite"]
        assert "    timeout-minutes: 30\n" in initial["tests"]
        repo.git("checkout", "-qb", "fix/full-run-budget", cwd=client)
    _settings(client, test="python -m pytest tests -q", groups=2)
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    jobs = _jobs((client / ".github/workflows/forge.yml").read_text(encoding="utf-8"))
    assert "group: [1, 2]" in jobs["full-suite"]
    assert "    timeout-minutes: 60\n" in jobs["full-suite"]
    assert "    timeout-minutes: 30\n" in jobs["tests"]
