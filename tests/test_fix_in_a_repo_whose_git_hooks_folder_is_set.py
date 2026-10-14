"""Git hooks configured in a Husky-style folder."""
from __future__ import annotations

STORY = "FIX-IN-A-REPO-WHOSE-GIT-HOOKS-FOLDER-IS-SET"


def _client(repo):
    repo.git("checkout", "-q", "-b", "fix/husky")
    repo.write("forge.toml", f'version = "{repo.forge("--version").stdout.split()[-1]}"\n'
                             'test = "true"\nchecks = ["tests", "forge-pr-check"]\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Set up client")
    repo.git("config", "core.hooksPath", ".husky/_")
    hooks = repo.path / ".husky" / "_"
    hooks.mkdir(parents=True)
    return hooks


def test_2_doctor_reports_missing_hooks_in_husky_folder(repo):
    hooks = _client(repo)
    with (repo.path / "forge.toml").open("a", encoding="utf-8") as config:
        config.write('repo = "forge-source"\n')
    done = repo.forge("doctor")
    assert done.returncode == 1
    # Husky's committed hooks are synced files; its generated dispatchers aren't Forge shims.
    assert ".husky/pre-commit differs from what forge sync writes" in done.stdout
    assert ".husky/pre-push differs from what forge sync writes" in done.stdout
    # FORGE-DOCTORFIX-1 changed the Fix from forge sync: doctor --fix now puts the hooks back.
    assert "Fix: forge doctor --fix" in done.stdout

    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    assert (hooks.parent / "pre-commit").exists() and (hooks.parent / "pre-push").exists()
    assert not (hooks / "pre-commit").exists() and not (hooks / "pre-push").exists()
    done = repo.forge("doctor")
    assert "The git hooks that check each commit and push aren't installed." not in done.stdout
