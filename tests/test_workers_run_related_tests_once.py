"""Workers run their related tests once a turn and never poll the machine lines."""
from test_workers_leave_settings_to_coordinator import client  # noqa: F401
from test_worker import calls, install_claude

STORY = "worker-tests-once"


def test_1_worker_brief_says_run_related_tests_once_without_polling(client):
    # The brief forge work sends is the contract; the stub only records it.
    log = install_claude(client)
    started = client.forge("fix", "start", "Check worker test guidance", "--done",
                           "Workers run related tests once")
    assert started.returncode == 0, started.stdout + started.stderr
    worked = client.forge("work", "check-worker-test-guidance")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[0]["brief"].split())
    assert ("Run the related tests once, at the end of your turn, and rerun only what failed. "
            "Never poll `forge lanes --json` or `forge board --json` and never tail test logs "
            "while you wait.") in brief
