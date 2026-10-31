"""Worker permission requests reach Forge rather than an automatic refusal."""
from test_codex_worker import _codex_repo, _sent, sdk_data  # noqa: F401

STORY = "codex-builders-must-write-a-failing-test"


def test_1_worker_requests_use_forges_accepting_reviewer(repo, monkeypatch, sdk_data, claude_session):
    _folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    # First build and resumed fix rounds must both let commands such as forge test ask
    # Forge's accepting handler. "never" refuses escalation before that handler runs;
    # auto_review delegates the choice to another model instead of Forge.
    for _ in range(2):
        built = repo.forge("work", "BOARD/PAGE")
        assert built.returncode == 0, built.stdout + built.stderr
    fixed = repo.forge("fix", "start", "Allow the test command", "--done", "Tests can run")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    built = repo.forge("work", "allow-the-test-command")
    assert built.returncode == 0, built.stdout + built.stderr
    for method in ("thread/start", "thread/resume", "turn/start"):
        sent = _sent(calls, method)
        assert sent, method
        for params in sent:
            assert params["approvalPolicy"] == "on-request"
            assert params["approvalsReviewer"] == "user"
