"""Close incorporates a default-branch release before validating generated files."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import GREEN, env  # noqa: F401
from test_running_commands_follow_changed_forge_pin import _earlier_release
from test_setup import _fresh_client

STORY = "close-behind-version-bump"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
@pytest.mark.platform
def test_1_close_merges_default_release_before_upgrade_validation(env, adopted, monkeypatch):
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
    hooks = Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    assert (hooks / "pre-commit").is_file()
    item, where = env.start_fix()

    # An upstream upgrade changes generated files too. Its commit uses the new release's
    # real hooks; publishing it to main stands in for GitHub merging that release.
    _, upgrade = env.start("release", "fix/release", ".factory/fixes/release.json",
                           {"kind": "fix", "why": "Upgrade Forge",
                            "done_when": "forge.toml pins the new Forge release"}, {})
    old = (upgrade / "forge.toml").read_text("utf-8")
    upgraded = old.replace('version = "v1.2.2"', f'version = "{current}"\nfast_test = ""')
    (upgrade / "forge.toml").write_bytes(upgraded.encode("utf-8"))
    launcher = env.tmp / "current-bin" / "forge"
    with monkeypatch.context() as selected:
        selected.setenv("PATH", f"{launcher.parent}{os.pathsep}{os.environ['PATH']}")
        selected.setenv("FORGE_PINNED_RUN", current)
        synced = subprocess.run([sys.executable, str(launcher), "sync"], cwd=upgrade,
                                capture_output=True, text=True, timeout=120)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        env.commit(upgrade, "forge.toml", upgraded, "Upgrade Forge and its generated files")
    changed = repo.git("diff", "--name-only", "HEAD^", "HEAD", cwd=upgrade).splitlines()
    assert ".forge/hooks.sh" in changed
    release = repo.git("rev-parse", "HEAD", cwd=upgrade)
    repo.git("-c", f"core.hooksPath={env.tmp / 'no-hooks'}", "push", "-q", "origin",
             "fix/release:main", cwd=upgrade)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    assert "uv tool install" not in closed.stdout + closed.stderr
    assert repo.git("merge-base", "HEAD", release, cwd=where) == release
    assert (where / "forge.toml").read_text("utf-8") == upgraded
    assert (where / ".forge/hooks.sh").read_bytes() == (upgrade / ".forge/hooks.sh").read_bytes()


def test_2_close_allows_default_without_settings_during_adoption(env):
    repo = env.repo
    repo.git("rm", "forge.toml")
    env.commit(repo.path, "README.md", "# A live app\n", "Keep the app before adoption")
    repo.git("push", "-q", "origin", "main")
    adopted = repo.forge("init", "--actions", "yes", "--test", "python -V",
                         "--checks", "tests", "--interfaces", "api/routes/**",
                         "--approver", "Owner", "--merger", "Owner")
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    writer = env.tmp / "teammate"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(writer))
    release = env.commit(writer, "other.txt", "A teammate's change\n")
    repo.git("push", "-q", "origin", "main", cwd=writer)

    closed = env.close("adopt-forge")

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    where = repo.path.parent / f"{repo.path.name}-fix-adopt-forge"
    assert repo.git("merge-base", "HEAD", release, cwd=where) == release
