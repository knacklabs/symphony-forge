"""Workers receive the CI handoff instruction on new and upgraded clients."""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "brief-close-pushes"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
def test_1_workers_commit_and_stop_when_they_need_ci_evidence(repo, gh, tmp_path, previous):
    # Prompt delivery is the contract; the Claude stub only records Forge's actual input.
    # The earlier adoption is release output from a text fixture, not today's sync output.
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    repo.git("switch", "-q", "-c", "fix/ci-guidance")
    version = repo.forge("--version").stdout.split()[-1]
    config = (repo.path / "forge.toml").read_text("utf-8")
    config = config.replace('version = "v1.2.2"', f'version = "{version}"')
    config = config.replace('workers = "codex"', 'workers = "claude"').replace(
        'workers = "split"', 'workers = "claude"')
    repo.write("forge.toml", config)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A")
    # Seed a landed setup before the client has an active fix, as the upgrade tests do.
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-q", "-m",
             "Upgrade worker guidance")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/ci-guidance")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main")
    log = install_claude(repo)
    started = repo.forge("fix", "start", "Check worker CI guidance", "--done",
                         "Workers leave CI to close")
    assert started.returncode == 0, started.stdout + started.stderr
    for round_number in (1, 2):
        worked = repo.forge("work", "check-worker-ci-guidance")
        assert worked.returncode == 0, worked.stdout + worked.stderr
        call = calls(log)[-1]
        assert ("--resume" in call["args"]) == (round_number == 2)
        brief = " ".join(call["brief"].split())
        assert "`forge close` pushes the committed branch and runs CI on every platform." in brief
        assert "CI output reaches you in your next round." in brief
        assert ("If you need CI evidence, commit and stop instead of asking the coordinator "
                "to push or run CI.") in brief
