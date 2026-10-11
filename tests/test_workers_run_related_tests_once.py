"""Fresh, nudged and resumed workers receive the same bounded test instruction."""
from test_workers_leave_settings_to_coordinator import client  # noqa: F401
from test_worker import calls, install_claude

STORY = "worker-tests-once"


def test_1_workers_run_related_tests_once_without_polling(client, monkeypatch):
    # Prompt delivery is the contract; the stub records actual input without deciding it.
    # Previously workers had no limit on repeated runs or machine-line watching.
    log = install_claude(client)
    started = client.forge("fix", "start", "Check worker test guidance", "--done",
                           "Workers run related tests once")
    assert started.returncode == 0, started.stdout + started.stderr
    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "change.txt")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "2")
    for round_number in (1, 2):
        worked = client.forge("work", "check-worker-test-guidance")
        assert worked.returncode == 0, worked.stdout + worked.stderr
        if round_number == 1:
            monkeypatch.delenv("STUB_CLAUDE_LEAVE")
            monkeypatch.delenv("STUB_CLAUDE_COMMIT_FROM")
    delivered = calls(log)
    assert len(delivered) == 3  # Fresh brief, commit nudge, resumed brief.
    assert "--resume" in delivered[-1]["args"]
    for call in delivered:
        brief = " ".join(call["brief"].split())
        assert "Run the related tests once at the end of your turn; rerun only what failed." in brief
        assert "Never poll machine lines (`forge lanes --json` or `forge board --json`) or tail test logs while waiting." in brief
        assert "Keep required red-before-fix regression checks." in brief
        assert "Wait for the foreground test command to finish." in brief
