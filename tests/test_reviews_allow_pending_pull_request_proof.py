"""Review-prompt delivery contracts; these do not prove a model follows the rule."""
import shutil
from pathlib import Path

import pytest

from conftest import Repo
from test_close import GREEN, env, run  # noqa: F401
from test_setup import _fresh_client

STORY = "FIX-PENDING-CI-PROOF"


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "sync-after-v1.2.2"])
def test_1_review_defers_pending_pr_check_proof_but_keeps_failed_or_absent_proof_p1(
        env, tmp_path, adopted):
    repo = env.repo
    config = (repo.path / "forge.toml").read_text("utf-8")
    if adopted:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Adopt on the earlier release")
        client = repo.path
    else:
        client, initialized = _fresh_client(repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    env.repo = Repo(client, repo.bin)
    if adopted:
        env.commit(client, "forge.toml", config, "Use the installed Forge")
    env.repo.git("push", "-q", "origin", "main")
    started = env.repo.forge("fix", "start", "Scan the client image", "--done",
                             "The image scan pull request check proves the image is safe")
    assert started.returncode == 0, started.stdout + started.stderr
    where = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    if not adopted:
        env.commit(where, "forge.toml", config, "Configure the client's checks")
    if adopted:
        synced = env.repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    env.commit(where, "README.md", "# Scan the client image\n", "Describe the scan")
    env.checks(GREEN + [run("image scan", None, "in_progress")])
    closed = env.close("scan-the-client-image")
    assert closed.returncode != 0
    assert "image scan is still running" in closed.stdout + closed.stderr
    prompt = " ".join(env.prompt().split())
    # Old contract called unfinished CI proof Not done; the checks gate already waits for it.
    assert ("When a Done-when item's named proof is a pull request check that has not finished "
            "yet, do not report it as `Not done` if the check is configured to run on the pull "
            "request.") in prompt
    assert "Close's checks gate holds the merge until that check passes." in prompt
    assert "A failed check or a proof with no check behind it is still P1 `Not done`." in prompt
