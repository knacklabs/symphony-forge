"""The real command explains an old branch's pin after an upgrade lands.

Only uv is faked at its edge. Existing pin tests never land an upgrade while
retaining a pre-upgrade branch, so they cannot catch the missing merge advice.
"""
import shutil
import tomllib

import pytest

from conftest import ROOT
from test_fix_when_the_installed_forge_differs_from_th import _calls, _uv
from test_setup import _fresh_client, _version

STORY = "old-branch-pin"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_old_branches_explain_the_pin_after_a_fetched_upgrade(repo, gh, tmp_path, adopted):
    version = _version(repo)
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
        for host in (".codex", ".claude"):
            skill = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
            assert "merge `origin/<default>` into" in skill

    repo.git("switch", "-q", "-c", "setup")
    settings = (repo.path / "forge.toml").read_text("utf-8")
    pin = tomllib.loads(settings)["version"]
    settings = settings.replace(f'version = "{pin}"', 'version = "v1.2.2"')
    repo.write("forge.toml", settings)
    repo.git("add", "-A")
    no_hooks = f"core.hooksPath={tmp_path / 'no-hooks'}"
    repo.git("-c", no_hooks, "commit", "-q", "-m", "Adopt Forge")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "setup")
    repo.git("-c", no_hooks, "push", "-q", "origin", "main")
    repo.git("switch", "-q", "-c", "fix/old-work")
    log = _uv(repo)
    notice = f"Merge origin/main into this branch to use Forge {version} and its rules."
    command = ("fix", "start", "Tidy the readme", "--done", "It reads well")
    before = repo.forge(*command)
    assert before.returncode == 3
    original = (f"Forge {version} is installed, but this repo pins v1.2.2, so v1.2.2 "
                "runs through uv.\n")
    assert before.stderr == original

    # Land the upgraded pin and the real installed release's sync output.
    repo.git("switch", "-q", "-c", "fix/upgrade", "main")
    repo.write("forge.toml", settings.replace('version = "v1.2.2"', f'version = "{version}"'))
    upgraded = repo.forge("sync")
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    repo.git("add", "-A")
    repo.git("-c", no_hooks, "commit", "-q", "-m", "Upgrade Forge")
    repo.git("-c", no_hooks, "push", "-q", "origin", "fix/upgrade:main")
    repo.git("fetch", "-q", "origin")
    repo.git("switch", "-q", "fix/old-work")
    ran = repo.forge(*command)
    assert ran.returncode == 3
    assert ran.stderr == original.rstrip() + f" {notice}\n"
    assert _calls(log)[-1]["args"][3].endswith("@v1.2.2")

    # Even a stale local default is not told to merge itself.
    repo.git("switch", "-q", "main")
    stale = repo.forge(*command)
    assert stale.returncode == 3
    assert stale.stderr == original
    repo.git("merge", "-q", "--ff-only", "origin/main")
    calls = len(_calls(log))
    for branch in ("main", "fix/old-work"):
        repo.git("switch", "-q", branch)
        if branch != "main":
            repo.git("merge", "-q", "--ff-only", "main")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert notice not in synced.stdout + synced.stderr
        for host in (".codex", ".claude"):
            skill = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
            assert "merge `origin/<default>` into" in skill
    assert len(_calls(log)) == calls

    repo.write("forge.toml", settings.replace('version = "v1.2.2"', 'version = "v99.0.0"'))
    newer = repo.forge(*command)
    assert newer.returncode == 3
    assert newer.stderr == (f"Forge {version} is installed, but this repo pins v99.0.0, so "
                            "v99.0.0 runs through uv.\n")

    repo.git("checkout", "-q", "--detach")
    repo.write("forge.toml", settings)
    detached = repo.forge(*command)
    assert detached.returncode == 3
    assert detached.stderr == original

    repo.git("switch", "-q", "fix/old-work")
    repo.git("remote", "remove", "origin")
    unfetched = repo.forge(*command)
    assert unfetched.returncode == 3
    assert unfetched.stderr == original
