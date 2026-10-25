"""Worker briefs follow the repo's test place and never poll the machine lines."""
import re

import pytest

from test_workers_leave_settings_to_coordinator import client  # noqa: F401
from test_worker import calls, install_claude

STORY = "worker-tests-once"


def test_1_worker_brief_uses_test_place_instructions_without_polling(client):
    # The brief forge work sends is the contract; the stub only records it.
    config = (client.path / "forge.toml").read_text("utf-8")
    config = re.sub(r"(?m)^test_place\s*=.*\n", "", config)
    config = re.sub(r"(?m)^checks\s*=.*$", "checks = []", config)
    config = 'test_place = "local"\n' + config
    client.write("forge.toml", config)
    client.git("add", "forge.toml")
    client.git("commit", "-q", "-m", "Select laptop tests")
    client.git("push", "-q", "origin", "main")
    log = install_claude(client)
    started = client.forge("fix", "start", "Check worker test guidance", "--done",
                           "Workers run related tests once", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    worked = client.forge("work", "check-worker-test-guidance")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[0]["brief"].split())
    assert ("run the change's related tests through `forge test` in the foreground once, at the "
            "end of your turn. wait for it to finish; rerun only what failed.") in brief.lower()
    assert ("never poll `forge lanes --json` or `forge board --json` and never tail test logs "
            "while you wait.") in brief.lower()


@pytest.mark.platform
@pytest.mark.parametrize("test_place", ["local", "ci"])
def test_2_worker_test_guidance_follows_the_repo_test_place(repo, monkeypatch, test_place):
    # forge work owns the prompt contract: local workers run related tests, while CI workers
    # leave those tests to the pull request. The stub records Forge's prompt without choosing it.
    log = install_claude(repo)
    version = repo.forge("--version").stdout.split()[-1]
    checks = '["tests"]' if test_place == "ci" else "[]"
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
                             'workers = "claude"\n'
                             f'test_place = "{test_place}"\nchecks = {checks}\n'
                             'test = "python -c \\\"print(123)\\\""\n'
                             'models.fix = { model = "sonnet", effort = "medium" }\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Set the test place")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("fix", "start", "Check worker test guidance", "--done",
                         "Workers follow the repo test place", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr

    monkeypatch.setenv("STUB_CLAUDE_LEAVE", "worker-change.txt")
    monkeypatch.setenv("STUB_CLAUDE_COMMIT_FROM", "2")
    built = repo.forge("work", "check-worker-test-guidance")
    assert built.returncode == 0, built.stdout + built.stderr
    first, nudge = [" ".join(call["brief"].split()).lower() for call in calls(log)]

    monkeypatch.delenv("STUB_CLAUDE_LEAVE")
    monkeypatch.delenv("STUB_CLAUDE_COMMIT_FROM")
    resumed = repo.forge("work", "check-worker-test-guidance")
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    continued = " ".join(calls(log)[-1]["brief"].split()).lower()

    if test_place == "ci":
        guidance = ("the pull request's ci runs the change's related tests, lint and type checks, "
                    "so do not run them here; run `forge test` only for a test you are writing, "
                    "to watch it fail.")
        for brief in (first, nudge, continued):
            assert guidance in brief
            assert "run the change's related tests through `forge test` in the foreground" not in brief
    else:
        guidance = ("run the change's related tests through `forge test` in the foreground once, "
                    "at the end of your turn. wait for it to finish; rerun only what failed.")
        for brief in (first, nudge, continued):
            assert guidance in brief
