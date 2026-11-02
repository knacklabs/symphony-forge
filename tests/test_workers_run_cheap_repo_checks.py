"""Cheap repo checks belong in the worker round, including CI-only repos."""
from test_workers_leave_settings_to_coordinator import client  # noqa: F401
from test_worker import calls, install_claude

STORY = "a-builder-round-that-fails-a-cheap-check"


def test_1_workers_run_cheap_checks_before_the_round_ends(client):
    # Prompt delivery is the independent contract. Losing this instruction defers
    # cheap failures to CI; existing CI guidance tests only protect that handoff.
    # The model stub records delivered instructions, not the asserted behavior.
    # New and earlier-adopted clients use real work and sync, with no new seam.
    log = install_claude(client)
    started = client.forge("fix", "start", "Correct spelling", "--done",
                           "Correct the spelling", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    for _ in range(2):
        worked = client.forge("work", "correct-spelling")
        assert worked.returncode == 0, worked.stdout + worked.stderr
        brief = " ".join(calls(log)[-1]["brief"].split())
        assert "Run the repo's documented cheap checks before you end each builder round." in brief
        assert "This step also applies when `test_place` is `ci`." in brief
        assert "Fix failures in this round, rerun the failed checks, then commit the repairs." in brief
