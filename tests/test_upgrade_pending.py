STORY = "FORGE-UPGRADE-1"
"""While a Forge upgrade waits for its merge, the default branch keeps working (Done-when 3), and a
command run from the wrong folder points at the right one (Done-when 4)."""

from test_story import DOC, claude_plan, hook, ready, setup

OLD = "v0.0.1"


def _pin_old(repo):
    """The default branch, here and on its remote, pins an older Forge than the installed one."""
    repo.write("forge.toml", f'version = "{OLD}"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Pin an older Forge")
    repo.git("push", "-q", "origin", "main")
    return repo.forge("--version").stdout.split()[-1]


def _upgrade(repo, tmp_path, version):
    """An upgrade fix's worktree that pins the installed Forge."""
    fix = tmp_path / "repo-fix-upgrade-forge"
    repo.git("worktree", "add", "-q", "-b", "fix/upgrade-forge", str(fix))
    (fix / "forge.toml").write_text(f'version = "{version}"\n', encoding="utf-8")
    repo.git("commit", "-q", "-am", "Upgrade Forge", cwd=fix)
    return fix


def _refused_as_today(result, version):
    assert result.returncode == 1
    assert result.stderr == (
        f"Forge {version} is installed, but this repo pins {OLD}.\n"
        f"Next: uv tool install git+https://github.com/knacklabs/symphony-forge@{OLD}\n")


def test_3_default_branch_keeps_working_while_upgrade_waits(repo, tmp_path, claude_payload, monkeypatch):
    # A mismatch runs the pinned release through uv; inside that run, a mismatch still refuses.
    monkeypatch.setenv("FORGE_PINNED_RUN", OLD)
    # Without an upgrade fix, the default branch refuses the newer Forge as before.
    version = _pin_old(repo)
    _refused_as_today(repo.forge("fix", "start", "Tidy the readme", "--done", "It reads well"), version)

    # With the upgrade fix waiting, the default branch starts work and names the fix.
    _upgrade(repo, tmp_path, version)
    started = repo.forge("fix", "start", "Tidy the readme", "--done", "It reads well")
    assert started.returncode == 0, started.stderr
    assert "upgrade-forge" in started.stderr
    assert "Started fix tidy-the-readme" in started.stdout

    # Once the upgrade's merge is fetched, the worktree left behind changes nothing, even with the
    # local default branch not yet updated.
    repo.git("push", "-q", "origin", "fix/upgrade-forge:main")
    repo.git("fetch", "-q", "origin")
    assert repo.git("show", "main:forge.toml") == f'version = "{OLD}"'
    _refused_as_today(repo.forge("fix", "start", "Fix a typo", "--done", "No typo"), version)

    # The approval hook warns on a version mismatch but approves as usual.
    repo.git("merge", "-q", "--ff-only", "origin/main")
    setup(repo)
    shop = ready(repo, "SHOP")
    for checkout in (repo.path, shop):  # both the hook's folder and the story's pin an older Forge
        text = (checkout / "forge.toml").read_text(encoding="utf-8")
        (checkout / "forge.toml").write_text(text.replace(version, OLD), encoding="utf-8")
    approved = hook(repo, claude_plan(claude_payload, DOC))
    assert approved.returncode == 0, approved.stderr
    assert "Recorded the approval of Shoppers can save a basket." in approved.stdout
    assert f"pins Forge {OLD}, but {version} is installed" in approved.stderr
    assert repo.git("log", "-1", "--format=%s", "story/SHOP").startswith("Approve the plan")


def test_4_close_from_the_wrong_folder_points_at_the_right_one(repo, tmp_path):
    version = _pin_old(repo)
    fix = _upgrade(repo, tmp_path, version)
    other = tmp_path / "repo-fix-other"
    repo.git("worktree", "add", "-q", "-b", "fix/other", str(other), "main")
    refused = repo.forge("close", "upgrade-forge", cwd=other)
    assert refused.returncode == 1
    assert refused.stderr == (
        f"upgrade-forge is checked out in {fix}, which pins Forge {version}; this folder pins {OLD}.\n"
        f"Next: cd {fix}, then forge close upgrade-forge\n")
