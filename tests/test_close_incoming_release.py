"""Close names the default-branch merge instead of an older release install."""
import json
import shutil

import pytest

from conftest import ROOT
from test_close import GREEN, env  # noqa: F401
from test_running_commands_follow_changed_forge_pin import _earlier_release
from test_setup import _fresh_client

STORY = "close-behind-version-bump"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
@pytest.mark.platform
def test_1_close_names_the_default_merge_for_an_older_branch_pin(env, adopted, monkeypatch):
    repo = env.repo
    current = repo.forge("--version").stdout.split()[-1]
    _earlier_release(env)
    monkeypatch.setenv("FORGE_PINNED_RUN", "v1.2.2")
    if adopted:
        repo.git("switch", "-q", "-c", "fix/setup")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        env.commit(repo.path, ".factory/fixes/setup.json", json.dumps(
            {"kind": "adopt", "branch": "fix/setup", "status": "working",
             "allow_large": "Restore the historical adoption fixture"}), "Restore adoption state")
        env.commit(repo.path, "README.md", "# An adopted client\n", "Use the earlier adoption")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Install the earlier release hooks")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/setup")
        repo.git("-c", f"core.hooksPath={env.tmp / 'no-hooks'}", "push", "-q", "origin", "main")
    else:
        client, initialized = _fresh_client(repo, env.gh, env.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
        env.checks(GREEN)
    item, where = env.start_fix()
    head = repo.git("rev-parse", "HEAD", cwd=where)
    writer = env.tmp / "upstream-release"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(writer))
    old = (writer / "forge.toml").read_text("utf-8")
    # fast_test is unknown to the earlier process. Close must name the merge without
    # validating those incoming settings or attempting the merge itself.
    upgraded = old.replace('version = "v1.2.2"', f'version = "{current}"\nfast_test = ""')
    env.commit(writer, "forge.toml", upgraded, "Upgrade Forge")
    repo.git("push", "-q", "origin", "main", cwd=writer)

    closed = env.close(item)

    assert closed.returncode != 0, closed.stdout + closed.stderr
    assert (f"This fix pins Forge v1.2.2, but the default branch pins Forge {current}.\n"
            f"Next: forge work {item} to merge the default branch, then forge close {item}\n"
            ) in closed.stdout + closed.stderr
    assert "uv tool install" not in closed.stdout + closed.stderr
    assert repo.git("rev-parse", "HEAD", cwd=where) == head
    assert (where / "forge.toml").read_text("utf-8") == old
