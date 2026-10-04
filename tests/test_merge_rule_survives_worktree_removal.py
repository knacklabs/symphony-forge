"""Merge rules use Forge on PATH even after the checkout that registered them is gone."""
import json
import shlex
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install

STORY = "forge-sync-points-git-s-merge-rule-for-t"
DRIVER = 'forge hook merge-roadmap %O %A %B'


def _commit(repo, cwd, message):
    # Test branches exercise Git's merge driver independently of Forge's lane admission.
    repo.git("add", "-A", cwd=cwd)
    repo.git("-c", "core.hooksPath=no-hooks", "commit", "-qm", message, cwd=cwd)


@pytest.mark.parametrize("setup", ["init", "sync", "doctor --fix", "doctor source"])
def test_1_merge_rule_survives_removing_the_worktree_that_registered_it(
        repo, gh, tmp_path, setup):
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')
    if setup == "init":
        client = tmp_path / "new-client"
        remote = tmp_path / "new-client.git"
        repo.git("init", "-q", "--bare", "-b", "main", str(remote))
        repo.git("init", "-q", "-b", "main", str(client))
        repo.git("remote", "add", "origin", str(remote), cwd=client)
        made = repo.forge("init", cwd=client)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        # Adopt a real existing repository with the previous release, then upgrade its pin.
        old = tmp_path / "previous-release"
        # A shipped release fixture keeps this real adoption runnable in CI's shallow clone.
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(
            python=sys.executable, src=str(old / "src")))
        adopted = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init",
                                  "--test", "echo ok", "--checks", "tests",
                                  "--interfaces", "api/routes/**", "--approver", "Owner",
                                  "--merger", "Owner"],
                                 cwd=repo.path, capture_output=True, text=True)
        assert adopted.returncode == 0, adopted.stdout + adopted.stderr
        client = repo.path.parent / f"{repo.path.name}-fix-adopt-forge"
        config = client / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text().replace('version = "v1.2.2"',
                                                     f'version = "{version}"'))
        assert "plans/spotted.json" not in (client / ".gitattributes").read_text()
        # Git runs this through sh even on Windows; the Python literal escapes backslashes.
        legacy_driver = shlex.split(repo.git("config", "--get", "merge.forge-roadmap.driver",
                                            cwd=client))
        assert repr(str(old / "src")) in legacy_driver[2]
        shutil.rmtree(old)
        if setup == "doctor source":
            config.write_text(config.read_text().replace('repo = "client"', 'repo = "forge-source"'))
        _commit(repo, client, "Upgrade the client pin")

    hooks = [repo.path / ".git/hooks" / name for name in ("pre-commit", "pre-push")]
    before_hooks = [path.read_bytes() if path.exists() else None for path in hooks]
    work = tmp_path / "sync-worktree"
    repo.git("worktree", "add", "-qb", "fix/register-rule", str(work), cwd=client)
    # Run real Forge from code in this disposable checkout, as a Forge source worker does.
    shutil.copytree(ROOT / "src", work / "src")
    _install(repo.bin, "work-forge", FORGE_SHIM.format(
        python=sys.executable, src=str(work / "src")))
    if setup != "init":
        command = ["sync"] if setup == "sync" else ["doctor", "--fix"]
        done = subprocess.run([sys.executable, str(repo.bin / "work-forge"), *command],
                              cwd=work, capture_output=True, text=True)
        if setup == "sync":
            assert done.returncode == 0, done.stdout + done.stderr
        else:
            # Other doctor checks may report missing third-party tools; only this repair is owned.
            assert done.returncode in (0, 1), done.stdout + done.stderr
        if setup == "doctor source":
            # Forge-source now repairs the previous release's stale hooks like a client repo.
            assert [path.read_bytes() if path.exists() else None for path in hooks] != before_hooks
            assert "- Fixed: installed the git hooks that check each commit and push." in done.stdout
    repo.git("worktree", "remove", "--force", str(work), cwd=client)
    driver = repo.git("config", "--get", "merge.forge-roadmap.driver", cwd=client)

    lists = ("plans/spotted.json", "plans/roadmap.json")
    for rel in lists:
        path = client / rel
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({"items": [{"key": "base", "status": "pending"}]}) + "\n")
    _commit(repo, client, "Base lists")
    other = tmp_path / "merge-worktree"
    repo.git("worktree", "add", "-qb", "fix/other-list", str(other), cwd=client)
    for cwd, key in ((client, "ours"), (other, "theirs")):
        for rel in lists:
            (cwd / rel).write_text(json.dumps({"items": [
                {"key": "base", "status": "pending"}, {"key": key, "status": "pending"}
            ]}, indent=2) + "\n")
        _commit(repo, cwd, f"Add {key}")
    merged = repo.git("-c", "core.hooksPath=no-hooks", "merge", "--no-edit",
                      "fix/other-list", cwd=client)
    assert "CONFLICT" not in merged
    assert len(repo.git("log", "-1", "--format=%P", cwd=client).split()) == 2
    for rel in lists:
        assert [item["key"] for item in json.loads((client / rel).read_text())["items"]] == [
            "base", "ours", "theirs"]
    assert repo.git("status", "--porcelain", cwd=client) == ""
    assert driver == DRIVER
