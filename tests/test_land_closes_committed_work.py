"""Hand-committed work goes directly through close, including after an upgrade."""
import json
import shutil
import sys

import pytest

from conftest import GH_STUB, ROOT, _install
from test_close import GREEN, env  # noqa: F401
from test_land import GH, URL, _steps, _workers, land  # noqa: F401

STORY = "forge-land-starts-a-worker-round-even-wh"


@pytest.mark.parametrize("history", ["new", "upgraded"])
def test_1_land_closes_a_hand_committed_fix_without_a_worker(land, history):
    # Audit: the real command must reach Ready without a worker call. The old started-status
    # shortcut runs a worker despite a hand commit; existing tests cover worker-made commits.
    # Only GitHub, the reviewer and the worker host are faked, with no production test seam.
    env, repo = land, land.repo
    if history == "new":
        remote, client = env.tmp / "client.git", env.tmp / "client"
        repo.git("init", "-q", "--bare", "-b", "main", str(remote))
        repo.git("init", "-q", "-b", "main", str(client))
        repo.git("remote", "add", "origin", str(remote), cwd=client)
        env.gh.respond("api", stdout="{}")
        made = repo.forge("init", cwd=client)
        assert made.returncode == 0, made.stderr
        repo.path = client
        _install(repo.bin, "gh", GH.format(python=sys.executable, remote=str(remote), url=URL)
                 + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    else:
        repo.git("switch", "-qc", "fix/upgrade-client")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the previous release")
        env.commit(repo.path, ".factory/fixes/upgrade-client.json", json.dumps({
            "kind": "fix", "branch": "fix/upgrade-client", "why": "Upgrade Forge",
            "done_when": "The client uses this release", "status": "started"}))
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text().replace('"v1.2.2"', json.dumps(version)))
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stderr
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade Forge")
        repo.git("switch", "main")
        repo.git("merge", "--ff-only", "fix/upgrade-client")
        checkout = env.tmp / "upgraded-client"
        repo.git("clone", "-q", str(repo.path), str(checkout))
        repo.path = checkout
        repo.git("remote", "set-url", "origin", str(env.tmp / "remote.git"))
        repo.git("push", "-q", "origin", "main")
    env.checks(GREEN)
    started = repo.forge("fix", "start", "Bump the package version", "--done",
                         "The package version is updated", "--slug", "bump-version")
    assert started.returncode == 0, started.stderr
    where = repo.path.parent / f"{repo.path.name}-fix-bump-version"
    env.commit(where, "VERSION", "2.0.0\n", "Bump the package version")
    before = (where / "forge.toml").read_text()
    done = repo.forge("land", "bump-version")
    assert _steps(done)[0] == "Closing bump-version.", done.stdout + done.stderr
    assert not _workers(env), done.stdout + done.stderr
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Ready: bump-version has a clean review" in done.stdout
    ref = "origin/fix/bump-version" if where.exists() else "origin/main"
    assert repo.git("show", f"{ref}:VERSION") == "2.0.0"
    assert repo.git("show", f"{ref}:forge.toml") == before.rstrip("\n")
